"""Shared helpers for the step by step scripts.

Every script reads the clipboard and/or the DB files, then copies the next
prompt to the clipboard. Anything wrong raises, so the .bat pauses on the error.

The menu is a flat list of ingredients with their amount for the day: there is no dish. An ingredient is a
SR Legacy food or a manual food (food_manual.csv), whose nutrients are in food_nutrient_manual.csv.
"""
import csv
import io
import math
import os
import re
from pathlib import Path

import pyperclip

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "DB"

DAILY_NEED_FILE = DB_DIR / "daily_need_table.csv"
NUTRIENT_FILE = DB_DIR / "nutrient.csv"
FOOD_FILE = DB_DIR / "food.csv"
FOOD_NUTRIENT_FILE = DB_DIR / "food_nutrient.csv"
FOOD_MANUAL_FILE = DB_DIR / "food_manual.csv"
FOOD_NUTRIENT_MANUAL_FILE = DB_DIR / "food_nutrient_manual.csv"
MENU_FILE = DB_DIR / "menu.csv"

# The amount of a food is in grams, its nutrients being given for 100g. A supplement taken as a pill has no
# meaningful weight: its amount is a number of doses, its nutrients being given for one dose.
GRAM, DOSE = "g", "dose"
UNITS = (GRAM, DOSE)

FOOD_MANUAL_HEADER = ["fdc_id", "description", "unit"]
MENU_HEADER = ["fdc_id", "description", "amount", "unit"]
# How the LLM writes the menu
MENU_ANSWER_HEADER = ["ingredient_fdc_id", "ingredient_description", "amount", "unit"]
# How it is shown to be checked: what the LLM meant, next to what its ID really is
MENU_CHECK_HEADER = ["ingredient_fdc_id", "ingredient_description", "real_description", "amount", "unit"]
# What the LLM writes as ingredient_fdc_id for an ingredient that is in no food database
NEW_INGREDIENT = "new"
FOOD_NUTRIENT_HEADER = [
    "id", "fdc_id", "nutrient_id", "amount", "data_points",
    "derivation_id", "min", "max", "median",
]

# Start of the prompt a check step gives back to Gemini when it finds an error itself
ERROR_PROMPT = "Your csv output is incorrect, write the whole corrected csv. The error is:"

# Given with every request for a food_nutrient csv
NUTRIENT_ID_NOTE = """When a row of daily_need_table.csv has several IDs (e.g. "1278, 1272"), the need is the sum of those nutrients: each of them must still have its own row with its single nutrient_id and its own amount. Never write a combined ID or a summed amount in the csv."""
NUTRIENT_UNIT_NOTE = f"""The amounts are for 100g of the food item when its unit is {GRAM}, for one dose when its unit is {DOSE}."""


# ---------------------------------------------------------
# Clipboard
# ---------------------------------------------------------
def get_clipboard():
    """Returns the clipboard text with normalized line endings; raises if it is empty."""
    text = pyperclip.paste().replace("\r\n", "\n")
    if not text.strip():
        raise ValueError("Clipboard is empty or contains no text.")
    return text


def set_clipboard(text):
    pyperclip.copy(text)
    print("The new prompt has been copied to your clipboard.")


def confirm(question):
    return input(f"{question} (y/n): ").strip().lower() in ("y", "yes")


# ---------------------------------------------------------
# CSV
# ---------------------------------------------------------
def _split_header(rows, source):
    """Drops the blank rows and returns (header, data rows)."""
    rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError(f"{source} is empty.")
    return rows[0], rows[1:]


def read_csv(path):
    """Reads a CSV file and returns (header, data rows)."""
    # 'utf-8-sig' ignores the BOM some of the DB files start with
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return _split_header(list(csv.reader(f)), path)


def check_header(header, expected, source):
    if [col.lower() for col in header] != expected:
        raise ValueError(f"CSV column mismatch in {source}!\nExpected: {expected}\nFound:    {header}")


def write_csv(path, header, rows):
    """Rewrites a whole CSV file, without leaving it half written if something fails."""
    tmp_path = Path(f"{path}.tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(tmp_path, path)


def rows_to_csv(header, rows):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().strip()


def file_block(name, csv_text):
    """Formats a CSV for a prompt: its name, then its content in a markdown block."""
    return f"{name}\n```csv\n{csv_text}\n```"


def extract_csv(text):
    """Returns the CSV text of an LLM answer, with or without a markdown block around it."""
    blocks = re.findall(r"```([^\n]*)\n(.*?)```", text, re.DOTALL)
    # The LLM may show the code it ran before its answer: the answer is the last csv block, or else the last block
    csv_blocks = [content for language, content in blocks if language.strip().lower() == "csv"]
    csv_text = (csv_blocks or [content for _, content in blocks] or [text])[-1].strip()
    if not csv_text:
        raise ValueError("No CSV content found in the clipboard.")
    return csv_text


def _to_int(value, what):
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid {what}: '{value}' is not an integer.") from None


def _to_float(value, what):
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid {what}: '{value}' is not a number.") from None


# ---------------------------------------------------------
# Foods
# ---------------------------------------------------------
def load_manual_foods():
    """Returns the manual foods as a list of (fdc_id, description, unit); none if the file does not exist yet."""
    if not FOOD_MANUAL_FILE.exists():
        return []
    header, rows = read_csv(FOOD_MANUAL_FILE)
    # Written before the units: every food was in grams
    with_unit = [col.lower() for col in header] != FOOD_MANUAL_HEADER[:2]
    if with_unit:
        check_header(header, FOOD_MANUAL_HEADER, FOOD_MANUAL_FILE)
    foods = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(header) or not row[1] or (with_unit and row[2] not in UNITS):
            raise ValueError(f"Malformed row {line} in {FOOD_MANUAL_FILE}: {row}")
        fdc_id = _to_int(row[0], f"fdc_id at row {line} of {FOOD_MANUAL_FILE}")
        foods.append((fdc_id, row[1], row[2] if with_unit else GRAM))
    return foods


def load_food_manual():
    """Returns the manual foods as a list of (fdc_id, description)."""
    return [(fdc_id, description) for fdc_id, description, _ in load_manual_foods()]


def load_sr_legacy_foods():
    """Returns the SR Legacy foods as {fdc_id: description}."""
    header, rows = read_csv(FOOD_FILE)
    id_col, description_col = header.index("fdc_id"), header.index("description")
    return {int(row[id_col]): row[description_col] for row in rows}


def load_all_foods():
    """Returns the SR Legacy and the manual foods as {fdc_id: description}."""
    foods = load_sr_legacy_foods()
    foods.update(load_food_manual())
    return foods


def load_food_units():
    """Returns the unit of the manual foods as {fdc_id: unit}. A SR Legacy food is always in grams."""
    return {fdc_id: unit for fdc_id, _, unit in load_manual_foods()}


def add_manual_foods(new_foods):
    """Appends (description, unit) foods to food_manual.csv, with the smallest free IDs."""
    foods = load_manual_foods()
    # An ID that still has nutrients would give them to the new food
    used = set(load_sr_legacy_foods()) | {fdc_id for fdc_id, _, _ in foods} | manual_nutrient_food_ids()
    current_id = 1
    for description, unit in new_foods:
        while current_id in used:
            current_id += 1
        foods.append((current_id, description, unit))
        used.add(current_id)
    write_csv(FOOD_MANUAL_FILE, FOOD_MANUAL_HEADER, foods)
    print(f"Successfully added {len(new_foods)} foods to '{FOOD_MANUAL_FILE}'.")


def food_manual_block(foods):
    """Formats (fdc_id, description, unit) manual foods for a prompt."""
    return file_block(FOOD_MANUAL_FILE.name, rows_to_csv(FOOD_MANUAL_HEADER, foods))


# ---------------------------------------------------------
# Food search
# ---------------------------------------------------------
def _words(description):
    """Returns the words of a food description, without their plural, to compare descriptions."""
    return {word.rstrip("s") for word in re.findall(r"[a-z]+", description.lower()) if len(word) > 2}


def same_description(a, b):
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def food_candidates(descriptions, foods, limit=10):
    """Returns the foods ({fdc_id: description}) the closest to each description, as {description: [(fdc_id, description)]}."""
    index = {fdc_id: _words(description) for fdc_id, description in foods.items()}
    counts = {}
    for words in index.values():
        for word in words:
            counts[word] = counts.get(word, 0) + 1

    candidates = {}
    for description in dict.fromkeys(descriptions):
        wanted = _words(description)
        # What comes before the first comma names the food ("Broccoli, stir-fried"): it counts more than its state
        named = _words(description.split(",")[0])
        scored = []
        for fdc_id, words in index.items():
            # A rare word ("kale") tells more than a common one ("raw")
            score = sum(
                math.log(len(index) / counts[word]) * (3 if word in named else 1) for word in wanted & words
            )
            if score:
                scored.append((-score, len(words - wanted), fdc_id))
        candidates[description] = [(fdc_id, foods[fdc_id]) for _, _, fdc_id in sorted(scored)[:limit]]
    return candidates


def candidates_block(descriptions, foods):
    """Formats the foods ({fdc_id: description}) the closest to each description for a prompt."""
    return "\n".join(
        f'- "{description}":'
        + ("".join(f"\n  {fdc_id}: {found}" for fdc_id, found in candidates) or "\n  nothing found")
        for description, candidates in food_candidates(descriptions, foods).items()
    )


# ---------------------------------------------------------
# Menu
# ---------------------------------------------------------
def load_menu():
    """Returns the rows of menu.csv, as [fdc_id, description, amount, unit].

    fdc_id is empty for an ingredient that is not identified yet. description is the one the LLM gave.
    """
    if not MENU_FILE.exists():
        raise ValueError(f"{MENU_FILE.name} does not exist yet: run step 2.5 first.")
    header, rows = read_csv(MENU_FILE)
    check_header(header, MENU_HEADER, MENU_FILE)
    return rows


def load_identified_menu():
    """Returns the menu as a list of (fdc_id, amount, unit); raises while an ingredient has no ID."""
    rows = load_menu()
    without_id = [description for fdc_id, description, _, _ in rows if not fdc_id]
    if without_id:
        raise ValueError(
            f"Those ingredients of {MENU_FILE.name} have no ID yet, finish step 2.5 first: {', '.join(without_id)}"
        )
    if not rows:
        raise ValueError(f"{MENU_FILE.name} has no ingredient: run step 2.5 first.")
    return [(int(fdc_id), float(amount), unit) for fdc_id, _, amount, unit in rows]


def save_menu(rows):
    """Writes the whole menu (see load_menu) to menu.csv."""
    write_csv(MENU_FILE, MENU_HEADER, rows)
    print(f"Successfully wrote the {len(rows)} ingredients of the menu to '{MENU_FILE}'.")


def menu_check_block(rows, foods):
    """Formats the menu (see load_menu) to be checked: the description the LLM gave to each ingredient next to
    the real one of its ID, from foods ({fdc_id: description})."""
    return file_block(
        f"{MENU_FILE.name} (amount: for the whole day, in the unit of the row)",
        rows_to_csv(
            MENU_CHECK_HEADER,
            [
                [fdc_id, description, foods[int(fdc_id)] if fdc_id else "", amount, unit]
                for fdc_id, description, amount, unit in rows
            ],
        ),
    )


def parse_menu_csv(text, foods, units):
    """Strictly validates a menu CSV answer and returns its rows (see load_menu).

    foods ({fdc_id: description}) are the foods an ingredient can be, units ({fdc_id: unit}) the unit of the
    manual ones. Without ingredient_fdc_id, or with NEW_INGREDIENT instead (kept as it is in the rows), the row
    needs a description.
    """
    header, rows = _split_header(list(csv.reader(io.StringIO(extract_csv(text)))), "The clipboard CSV")
    columns = [col.lower() for col in header]
    # The LLM may also answer with the columns of the table it was shown
    if columns != MENU_CHECK_HEADER:
        check_header(header, MENU_ANSWER_HEADER, "the clipboard")
    if not rows:
        raise ValueError("No data rows found in the clipboard CSV (only header).")

    parsed = []
    unknown = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(columns):
            raise ValueError(
                f"Malformed CSV at row {line}: expected {len(columns)} columns, but found {len(row)}.\nRow data: {row}"
            )
        record = dict(zip(columns, row))
        description = record["ingredient_description"]
        amount = _to_float(record["amount"], f"amount at row {line}")
        unit = record["unit"].lower()
        if amount <= 0:
            raise ValueError(f"Invalid amount {amount} at row {line}.")
        if unit not in UNITS:
            raise ValueError(f"Invalid unit '{record['unit']}' at row {line}: it must be {GRAM} or {DOSE}.")

        ingredient_id = record["ingredient_fdc_id"].lower()
        if ingredient_id in ("", NEW_INGREDIENT):
            if not description:
                raise ValueError(f"Row {line} has neither an ingredient_fdc_id nor an ingredient_description.")
        else:
            ingredient_id = _to_int(ingredient_id, f"ingredient_fdc_id at row {line}")
            if ingredient_id not in foods:
                unknown.append((line, ingredient_id, description))
            elif unit != units.get(ingredient_id, GRAM):
                raise ValueError(
                    f"Wrong unit '{unit}' at row {line}: the amount of the food {ingredient_id} "
                    f"({foods[ingredient_id]}) is in {units.get(ingredient_id, GRAM)}."
                )
        parsed.append([str(ingredient_id), description, f"{amount:g}", unit])

    # All of them at once, so that the LLM corrects them in one go
    if unknown:
        message = (
            f"Those ingredient_fdc_id exist neither in SR Legacy 2018 (a SR Legacy fdc_id is between 167512 "
            f"and 175304, it is not a NDB number) nor in {FOOD_MANUAL_FILE.name}:\n"
            + "\n".join(f"- row {line}: {ingredient_id}" for line, ingredient_id, _ in unknown)
        )
        described = [description for _, _, description in unknown if description]
        if described:
            # Its memory of the IDs is not reliable: give it the real ones to choose from
            message += (
                "\nDo not guess another ID: take it from those foods, searched from your descriptions:\n"
                + candidates_block(described, foods)
            )
        raise ValueError(message)
    return parsed


# ---------------------------------------------------------
# Nutrients of the foods
# ---------------------------------------------------------
def manual_nutrient_food_ids():
    """Returns the IDs of the foods that have nutrients in food_nutrient_manual.csv."""
    if not FOOD_NUTRIENT_MANUAL_FILE.exists():
        return set()
    header, rows = read_csv(FOOD_NUTRIENT_MANUAL_FILE)
    check_header(header, FOOD_NUTRIENT_HEADER, FOOD_NUTRIENT_MANUAL_FILE)
    return {int(row[1]) for row in rows}


def save_to_nutrient_manual(rows):
    """Writes the validated nutrient rows to food_nutrient_manual.csv, replacing the rows of the same foods.

    Returns the rows as they are written, with their new IDs.
    """
    existing = []
    if FOOD_NUTRIENT_MANUAL_FILE.exists():
        header, existing = read_csv(FOOD_NUTRIENT_MANUAL_FILE)
        check_header(header, FOOD_NUTRIENT_HEADER, FOOD_NUTRIENT_MANUAL_FILE)

    # A food given again is replaced as a whole, so that none of its old rows remains
    new_foods = {row[1] for row in rows}
    kept = [row for row in existing if row[1] not in new_foods]
    replaced = sorted({int(row[1]) for row in existing if row[1] in new_foods})
    if replaced:
        print(f"Replacing the {len(existing) - len(kept)} existing nutrient records of the foods {replaced}.")

    # The IDs chosen by the LLM may already be used: renumber after the last one of the file
    next_id = max((int(row[0]) for row in existing), default=49999) + 1
    rows = [[next_id + i, *row[1:]] for i, row in enumerate(rows)]

    write_csv(FOOD_NUTRIENT_MANUAL_FILE, FOOD_NUTRIENT_HEADER, kept + rows)
    print(f"Successfully wrote {len(rows)} nutrient records to '{FOOD_NUTRIENT_MANUAL_FILE}'.")
    return rows


def load_food_nutrients(fdc_ids):
    """Returns the nutrients of the foods as {fdc_id: {nutrient_id: amount}}; a food without any nutrient is left out."""
    print("Loading databases...")
    db = {}
    for file in (FOOD_NUTRIENT_FILE, FOOD_NUTRIENT_MANUAL_FILE):
        if not file.exists():
            continue
        # 'utf-8-sig' prevents the ﻿ header bug common with Windows CSVs
        with open(file, "r", encoding="utf-8-sig", newline="") as f:
            for line, row in enumerate(csv.DictReader(f), start=2):
                try:
                    fdc_id = int(row["fdc_id"])
                    if fdc_id in fdc_ids:
                        db.setdefault(fdc_id, {})[int(row["nutrient_id"])] = float(row["amount"])
                except (KeyError, TypeError, ValueError) as e:
                    raise ValueError(f"Malformed row {line} in {file}: {row}") from e
    return db


def parse_food_nutrient_csv(text, known_fdc_ids):
    """Strictly validates a food_nutrient CSV answer and returns its data rows.

    Every food of the csv must have a row for every nutrient of daily_need_table.csv.
    """
    header, rows = _split_header(list(csv.reader(io.StringIO(extract_csv(text)))), "The clipboard CSV")
    check_header(header, FOOD_NUTRIENT_HEADER, "the clipboard")
    if not rows:
        raise ValueError("No data rows found in the clipboard CSV (only header).")

    seen = set()
    given = {}
    for line, row in enumerate(rows, start=2):
        if len(row) != len(FOOD_NUTRIENT_HEADER):
            raise ValueError(
                f"Malformed CSV at row {line}: expected {len(FOOD_NUTRIENT_HEADER)} columns, "
                f"but found {len(row)}.\nRow data: {row}"
            )
        fdc_id = _to_int(row[1], f"fdc_id at row {line}")
        nutrient_id = _to_int(row[2], f"nutrient_id at row {line}")
        if _to_float(row[3], f"amount at row {line}") < 0:
            raise ValueError(f"Negative amount at row {line}.")
        if fdc_id not in known_fdc_ids:
            raise ValueError(f"Unexpected fdc_id {fdc_id} at row {line}. Expected one of {sorted(known_fdc_ids)}.")
        if (fdc_id, nutrient_id) in seen:
            raise ValueError(f"Nutrient {nutrient_id} is given twice for the food {fdc_id} (row {line}).")
        seen.add((fdc_id, nutrient_id))
        given.setdefault(fdc_id, set()).add(nutrient_id)

    needed = {nutrient_id for need in load_daily_needs() for nutrient_id in need["ids"]}
    missing = [
        f"- food {fdc_id}: nutrient_id {', '.join(map(str, sorted(needed - nutrient_ids)))}"
        for fdc_id, nutrient_ids in given.items() if needed - nutrient_ids
    ]
    if missing:
        raise ValueError("Data missing for:\n" + "\n".join(missing))
    return rows


# ---------------------------------------------------------
# daily_need_table.csv
# ---------------------------------------------------------
def load_nutrients():
    """Returns the SR Legacy nutrients as {id: (name, unit)}."""
    header, rows = read_csv(NUTRIENT_FILE)
    id_col, name_col, unit_col = (header.index(col) for col in ("id", "name", "unit_name"))
    return {_to_int(row[id_col], f"id in {NUTRIENT_FILE}"): (row[name_col], row[unit_col]) for row in rows}


def load_daily_needs():
    """Returns the daily needs as a list of {ids, name, unit, min, max}.

    A need can cover several nutrients ("1278, 1272"): their amounts are summed.
    'ids' is empty for the rows without nutrient ID. 'max' is None when there is no limit.
    """
    nutrients = load_nutrients()

    header, rows = read_csv(DAILY_NEED_FILE)
    check_header(header, ["id", "name", "min", "max"], DAILY_NEED_FILE)
    needs = []
    for line, row in enumerate(rows, start=2):
        if len(row) != 4:
            raise ValueError(f"Malformed row {line} in {DAILY_NEED_FILE}: {row}")
        where = f"row {line} of {DAILY_NEED_FILE}"
        ids = [_to_int(i.strip(), f"nutrient id at {where}") for i in row[0].split(",") if i.strip()]
        unknown = [i for i in ids if i not in nutrients]
        if unknown:
            raise ValueError(f"Unknown nutrient id {unknown} at {where}.")
        if not ids:
            print(f"Warning: no nutrient id at {where}.")
        needs.append({
            "ids": ids,
            # The name of the table, or else the SR Legacy ones
            "name": row[1] or " + ".join(nutrients[i][0] for i in ids),
            "unit": "/".join(dict.fromkeys(nutrients[i][1] for i in ids)),
            "min": _to_float(row[2], f"min at {where}") if row[2] else 0.0,
            "max": _to_float(row[3], f"max at {where}") if row[3] else None,
        })
    return needs


def daily_need_block(with_targets=False):
    """Formats the daily need table for a prompt, with the nutrient names and units.

    Without the targets, the min and max columns are left out: only the list of the needed nutrients remains.
    """
    header = ["id", "name", "unit", "min", "max"]
    rows = [
        [", ".join(map(str, need["ids"])), need["name"], need["unit"], f"{need['min']:g}",
         "" if need["max"] is None else f"{need['max']:g}"]
        for need in load_daily_needs()
    ]
    if not with_targets:
        header, rows = header[:3], [row[:3] for row in rows]
    return file_block(DAILY_NEED_FILE.name, rows_to_csv(header, rows))
