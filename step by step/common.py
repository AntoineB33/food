"""Shared helpers for the step by step scripts.

Every script reads the clipboard and/or the DB files, then copies the next
prompt to the clipboard. Anything wrong raises, so the .bat pauses on the error.
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
FOOD_INGREDIENT_MANUAL_FILE = DB_DIR / "food_ingredient_manual.csv"
LAST_CHECKED_FILE = ROOT / "step by step bats" / "last_checked_food.txt"

FOOD_MANUAL_HEADER = ["fdc_id", "description"]
FOOD_INGREDIENT_HEADER = ["fdc_id", "ingredient_fdc_id", "quantity"]
# How the ingredients are shown in a prompt: the LLM may answer with this description column too
FOOD_INGREDIENT_DESCRIBED_HEADER = ["fdc_id", "ingredient_fdc_id", "ingredient_description", "quantity"]
# How they are shown to be checked: what the LLM meant, next to what its ID really is
FOOD_INGREDIENT_CHECK_HEADER = [
    "fdc_id", "ingredient_fdc_id", "ingredient_description", "real_description", "quantity",
]
# What the LLM writes as ingredient_fdc_id for an ingredient that is in no food database
NEW_INGREDIENT = "new"
FOOD_NUTRIENT_HEADER = [
    "id", "fdc_id", "nutrient_id", "amount", "data_points",
    "derivation_id", "min", "max", "median",
]

# Prompts shared by a step and its check
FOOD_LIST_PROMPT = """Provide me with a list of all food items (including prepared meals) on your menu that are not listed in the SR Legacy 2018 database (fdc.nal.usda.gov) and food_manual.csv. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu.
The list must be the names of the items, easy to copy."""

FOOD_QTT_PROMPT = """Write a text easy to copy in a csv format with two columns: food ID and quantity. For each food item (including prepared meals) on your menu, use the corresponding ID from SR Legacy 2018 (fdc.nal.usda.gov) and food_manual.csv (an extension of the main food database), and enter the quantity as a number where 1 means 100g. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu.
The food ID of a SR Legacy food is its fdc_id (between 167512 and 175304), not its NDB number."""


# Start of the prompt a check step gives back to Gemini when it finds an error itself
ERROR_PROMPT = "Your csv output is incorrect, write the whole corrected csv. The error is:"

# Given with every request for a food_nutrient csv
NUTRIENT_ID_NOTE = """When a row of daily_need_table.csv has several IDs (e.g. "1278, 1272"), the need is the sum of those nutrients: each of them must still have its own row with its single nutrient_id and its own amount. Never write a combined ID or a summed amount in the csv."""


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


def append_csv_rows(path, header, rows):
    """Appends rows to a CSV file, creating it with its header if needed."""
    path = Path(path)
    is_new = not path.exists() or path.stat().st_size == 0
    ends_with_newline = True
    if not is_new:
        check_header(read_csv(path)[0], header, path)
        with open(path, "rb") as f:
            f.seek(-1, 2)
            ends_with_newline = f.read(1) in (b"\n", b"\r")

    with open(path, "a", encoding="utf-8", newline="") as f:
        # Without this, the first new row would be glued to the last existing one
        if not ends_with_newline:
            f.write("\r\n")
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        if is_new:
            writer.writerow(header)
        writer.writerows(rows)


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
# food_manual.csv
# ---------------------------------------------------------
def load_food_manual():
    """Returns the manual foods as a list of (fdc_id, description); none if the file does not exist yet."""
    # add_new_foods creates the file with the first foods
    if not FOOD_MANUAL_FILE.exists():
        return []
    header, rows = read_csv(FOOD_MANUAL_FILE)
    check_header(header, FOOD_MANUAL_HEADER, FOOD_MANUAL_FILE)
    foods = []
    for line, row in enumerate(rows, start=2):
        if len(row) != 2 or not row[1]:
            raise ValueError(f"Malformed row {line} in {FOOD_MANUAL_FILE}: {row}")
        foods.append((_to_int(row[0], f"fdc_id at row {line} of {FOOD_MANUAL_FILE}"), row[1]))
    return foods


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


def parse_food_list(text):
    """Returns the food descriptions of the clipboard, one per line."""
    descriptions = []
    for i, line in enumerate(text.strip("\n").split("\n"), start=1):
        if not line or line.isspace():
            raise ValueError(f"Blank line detected at line {i}. Please fix the clipboard input.")
        if line[0].isspace():
            raise ValueError(f"Line {i} starts with a blank character. Please fix the clipboard input.")
        if line.strip().lower() in (d.lower() for d in descriptions):
            raise ValueError(f"'{line.strip()}' is listed twice (line {i}). Please fix the clipboard input.")
        descriptions.append(line.strip())
    return descriptions


def add_new_foods(descriptions, foods):
    """Appends the foods that are not in food_manual.csv yet, with the smallest free IDs."""
    known = {description.lower() for _, description in foods}
    for description in descriptions:
        if description.lower() in known:
            print(f"Already in {FOOD_MANUAL_FILE.name}, skipped: {description}")
    descriptions = [d for d in descriptions if d.lower() not in known]

    # The fdc_ids already used by SR Legacy and food_manual.csv
    existing_ids = set(load_sr_legacy_foods()) | {fdc_id for fdc_id, _ in foods}
    new_records = []
    current_id = 1
    for description in descriptions:
        while current_id in existing_ids:
            current_id += 1
        new_records.append([current_id, description])
        existing_ids.add(current_id)

    if new_records:
        append_csv_rows(FOOD_MANUAL_FILE, FOOD_MANUAL_HEADER, new_records)
    print(f"Successfully appended {len(new_records)} items to '{FOOD_MANUAL_FILE}'.")


def unchecked_foods(foods):
    """Returns the manual foods listed after the last checked one (all of them if none is checked)."""
    marker = LAST_CHECKED_FILE.read_text(encoding="utf-8-sig").strip() if LAST_CHECKED_FILE.exists() else ""
    if not marker:
        return foods
    positions = [i for i, (_, description) in enumerate(foods) if description.lower() == marker.lower()]
    if not positions:
        raise ValueError(f"Food description '{marker}' ({LAST_CHECKED_FILE}) was not found in {FOOD_MANUAL_FILE}.")
    return foods[positions[-1] + 1:]


def describe_diet(diet):
    """Returns the diet as rows of [fdc_id, description, quantity]; raises on the IDs that are in no food database."""
    descriptions = load_all_foods()

    unknown = [fdc_id for fdc_id in diet if fdc_id not in descriptions]
    if unknown:
        raise ValueError(
            f"The food IDs {unknown} are neither in {FOOD_FILE.name} (SR Legacy fdc_id) nor in {FOOD_MANUAL_FILE.name}."
        )
    return [[fdc_id, descriptions[fdc_id], f"{quantity:g}"] for fdc_id, quantity in diet.items()]


def load_diet_nutrients(diet):
    """Returns the nutrients of the foods of the diet as {fdc_id: {nutrient_id: amount}}.

    Raises on the IDs that are in no food database, and on the foods without any nutrient.
    """
    descriptions = {fdc_id: description for fdc_id, description, _ in describe_diet(diet)}

    print("Loading databases...")
    db = {}
    for file in (FOOD_NUTRIENT_FILE, FOOD_NUTRIENT_MANUAL_FILE):
        # 'utf-8-sig' prevents the ﻿ header bug common with Windows CSVs
        with open(file, "r", encoding="utf-8-sig", newline="") as f:
            for line, row in enumerate(csv.DictReader(f), start=2):
                try:
                    fdc_id = int(row["fdc_id"])
                    if fdc_id in diet:
                        db.setdefault(fdc_id, {})[int(row["nutrient_id"])] = float(row["amount"])
                except (KeyError, TypeError, ValueError) as e:
                    raise ValueError(f"Malformed row {line} in {file}: {row}") from e

    without_nutrient = [f"{fdc_id} ({descriptions[fdc_id]})" for fdc_id in diet if fdc_id not in db]
    if without_nutrient:
        raise ValueError(f"No nutrient in the databases for the foods: {', '.join(without_nutrient)}.")
    return db


def food_manual_block(foods):
    return file_block(FOOD_MANUAL_FILE.name, rows_to_csv(FOOD_MANUAL_HEADER, foods))


# ---------------------------------------------------------
# food_nutrient_manual.csv
# ---------------------------------------------------------
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


def ingredient_block(rows):
    """Formats ingredient rows (see load_food_ingredients) for a prompt, with the real description of each ingredient.

    An ingredient without ID keeps the description the LLM gave it.
    """
    foods = load_all_foods()
    return file_block(
        f"{FOOD_INGREDIENT_MANUAL_FILE.name} (quantity: 1 means 100g, in 100g of the food item)",
        rows_to_csv(
            FOOD_INGREDIENT_DESCRIBED_HEADER,
            [
                [fdc_id, ingredient_id, foods[int(ingredient_id)] if ingredient_id else description, quantity]
                for fdc_id, ingredient_id, description, quantity in rows
            ],
        ),
    )


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
    """Formats the foods ({fdc_id: description}) the closest to each description for a prompt; '' without description."""
    return "\n".join(
        f'- "{description}":'
        + ("".join(f"\n  {fdc_id}: {found}" for fdc_id, found in candidates) or "\n  nothing found")
        for description, candidates in food_candidates(descriptions, foods).items()
    )


def ingredient_check_block(rows, foods):
    """Formats ingredient rows (see load_food_ingredients) to be checked: the description the LLM gave to each
    ingredient next to the real one of its ID, from foods ({fdc_id: description})."""
    return file_block(
        f"{FOOD_INGREDIENT_MANUAL_FILE.name} (quantity: 1 means 100g, in 100g of the food item)",
        rows_to_csv(
            FOOD_INGREDIENT_CHECK_HEADER,
            [
                [fdc_id, ingredient_id, description, foods[int(ingredient_id)] if ingredient_id else "", quantity]
                for fdc_id, ingredient_id, description, quantity in rows
            ],
        ),
    )


def load_food_ingredients():
    """Returns the rows of food_ingredient_manual.csv, as [fdc_id, ingredient_fdc_id, ingredient_description, quantity].

    ingredient_fdc_id is the ID of a SR Legacy food or of another manual food. It is empty for an ingredient
    that is not identified yet: only its description tells what it is.
    """
    if not FOOD_INGREDIENT_MANUAL_FILE.exists():
        return []
    header, rows = read_csv(FOOD_INGREDIENT_MANUAL_FILE)
    if [col.lower() for col in header] == FOOD_INGREDIENT_HEADER:
        # Written before the descriptions were kept
        return [[row[0], row[1], "", row[2]] for row in rows]
    check_header(header, FOOD_INGREDIENT_DESCRIBED_HEADER, FOOD_INGREDIENT_MANUAL_FILE)
    return rows


def save_to_ingredient_manual(rows):
    """Writes ingredient rows (see load_food_ingredients) to food_ingredient_manual.csv, replacing the rows of the same foods."""
    new_foods = {row[0] for row in rows}
    kept = [row for row in load_food_ingredients() if row[0] not in new_foods]
    write_csv(FOOD_INGREDIENT_MANUAL_FILE, FOOD_INGREDIENT_DESCRIBED_HEADER, kept + rows)
    print(f"Successfully wrote {len(rows)} ingredient records to '{FOOD_INGREDIENT_MANUAL_FILE}'.")


def food_ingredient_block(fdc_ids):
    """Formats the saved ingredients of the foods for a prompt; None if they have none."""
    rows = [row for row in load_food_ingredients() if int(row[0]) in fdc_ids]
    return ingredient_block(rows) if rows else None


def updated_nutrient_blocks(foods, rows):
    """Returns the start of a prompt checking nutrient rows just saved: the needs, the foods, their ingredients, the rows."""
    blocks = [
        daily_need_block(),
        food_manual_block(foods),
        food_ingredient_block({fdc_id for fdc_id, _ in foods}),
        file_block("Rows updated in food_nutrient_manual.csv", rows_to_csv(FOOD_NUTRIENT_HEADER, rows)),
    ]
    return "\n\n".join(block for block in blocks if block)


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


# ---------------------------------------------------------
# LLM answers
# ---------------------------------------------------------
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


def parse_ingredient_csv(text, known_fdc_ids, foods):
    """Strictly validates a (food, ingredient, quantity) CSV answer and returns its rows (see load_food_ingredients).

    foods ({fdc_id: description}) are the foods an ingredient can be. Without ingredient_fdc_id, or with
    NEW_INGREDIENT instead (kept as it is in the rows), the row needs a description.
    """
    header, rows = _split_header(list(csv.reader(io.StringIO(extract_csv(text)))), "The clipboard CSV")
    columns = [col.lower() for col in header]
    # The descriptions are optional: the LLM may also answer with the columns of the table it was shown
    if columns not in (FOOD_INGREDIENT_HEADER, FOOD_INGREDIENT_CHECK_HEADER):
        check_header(header, FOOD_INGREDIENT_DESCRIBED_HEADER, "the clipboard")
    if not rows:
        raise ValueError("No data rows found in the clipboard CSV (only header).")

    parsed = []
    seen = set()
    unknown = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(columns):
            raise ValueError(
                f"Malformed CSV at row {line}: expected {len(columns)} columns, but found {len(row)}.\nRow data: {row}"
            )
        record = dict(zip(columns, row))
        fdc_id = _to_int(record["fdc_id"], f"fdc_id at row {line}")
        quantity = _to_float(record["quantity"], f"quantity at row {line}")
        description = record.get("ingredient_description", "")
        ingredient_id = record["ingredient_fdc_id"].lower()
        if ingredient_id in ("", NEW_INGREDIENT):
            if not description:
                raise ValueError(f"Row {line} has neither an ingredient_fdc_id nor an ingredient_description.")
        else:
            ingredient_id = _to_int(ingredient_id, f"ingredient_fdc_id at row {line}")
            if ingredient_id not in foods:
                unknown.append((line, ingredient_id, description))
            if ingredient_id == fdc_id:
                raise ValueError(f"The food {fdc_id} is given as its own ingredient (row {line}).")
        if fdc_id not in known_fdc_ids:
            raise ValueError(f"Unexpected fdc_id {fdc_id} at row {line}. Expected one of {sorted(known_fdc_ids)}.")
        if quantity <= 0:
            raise ValueError(f"Invalid quantity {quantity} at row {line}.")
        key = (fdc_id, ingredient_id if isinstance(ingredient_id, int) else description.lower())
        if key in seen:
            raise ValueError(f"The ingredient {key[1]} is given twice for the food {fdc_id} (row {line}).")
        seen.add(key)
        parsed.append([str(fdc_id), str(ingredient_id), description, f"{quantity:g}"])

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


def parse_diet_csv(text):
    """Strictly validates a (food ID, quantity) CSV answer and returns {fdc_id: quantity}."""
    rows = [
        [cell.strip() for cell in row]
        for row in csv.reader(io.StringIO(extract_csv(text))) if any(cell.strip() for cell in row)
    ]
    diet = {}
    for line, row in enumerate(rows, start=1):
        if len(row) != 2:
            raise ValueError(f"Malformed CSV at row {line}: expected 2 columns, but found {len(row)}.\nRow data: {row}")
        # The first row may be a header
        if line == 1 and not row[0].isdigit():
            continue
        fdc_id = _to_int(row[0], f"food ID at row {line}")
        quantity = _to_float(row[1], f"quantity at row {line}")
        if quantity <= 0:
            raise ValueError(f"Invalid quantity {quantity} at row {line}.")
        diet[fdc_id] = diet.get(fdc_id, 0.0) + quantity
    if not diet:
        raise ValueError("No data rows found in the clipboard CSV.")
    return diet
