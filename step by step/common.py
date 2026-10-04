"""Shared helpers for the step by step scripts.

Every script reads the clipboard and/or the DB files, then copies the next
prompt to the clipboard. Anything wrong raises, so the .bat pauses on the error.
"""
import csv
import io
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
LAST_CHECKED_FILE = ROOT / "step by step bats" / "last_checked_food.txt"

FOOD_MANUAL_HEADER = ["fdc_id", "description"]
FOOD_NUTRIENT_HEADER = [
    "id", "fdc_id", "nutrient_id", "amount", "data_points",
    "derivation_id", "min", "max", "median",
]

# Prompts shared by a step and its check
FOOD_LIST_PROMPT = """Provide me with a list of all food items (including prepared meals) on your menu that are not listed in the SR Legacy 2018 database (fdc.nal.usda.gov) and food_manual.csv. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu.
The list must be the names of the items, easy to copy."""

FOOD_QTT_PROMPT = """Write a text easy to copy in a csv format with two columns: food ID and quantity. For each food item (including prepared meals) on your menu, use the corresponding ID from SR Legacy 2018 (fdc.nal.usda.gov) and food_manual.csv (an extension of the main food database), and enter the quantity as a number where 1 means 100g. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu.
The food ID of a SR Legacy food is its fdc_id (between 167512 and 175304), not its NDB number."""


# Shared by the nutrient prompt (step 3.0) and its check (step 3.5)
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
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    csv_text = (match.group(1) if match else text).strip()
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
    """Returns the manual foods as a list of (fdc_id, description)."""
    header, rows = read_csv(FOOD_MANUAL_FILE)
    check_header(header, FOOD_MANUAL_HEADER, FOOD_MANUAL_FILE)
    foods = []
    for line, row in enumerate(rows, start=2):
        if len(row) != 2 or not row[1]:
            raise ValueError(f"Malformed row {line} in {FOOD_MANUAL_FILE}: {row}")
        foods.append((_to_int(row[0], f"fdc_id at row {line} of {FOOD_MANUAL_FILE}"), row[1]))
    return foods


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
    header, rows = read_csv(FOOD_FILE)
    id_col, description_col = header.index("fdc_id"), header.index("description")
    descriptions = {int(row[id_col]): row[description_col] for row in rows}
    descriptions.update(load_food_manual())

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
# daily_need_table.csv
# ---------------------------------------------------------
def load_daily_needs():
    """Returns the daily needs as a list of {ids, name, unit, min, max}.

    A need can cover several nutrients ("1278, 1272"): their amounts are summed.
    'ids' is empty for the rows without nutrient ID. 'max' is None when there is no limit.
    """
    header, rows = read_csv(NUTRIENT_FILE)
    id_col, name_col, unit_col = (header.index(col) for col in ("id", "name", "unit_name"))
    nutrients = {_to_int(row[id_col], f"id in {NUTRIENT_FILE}"): (row[name_col], row[unit_col]) for row in rows}

    header, rows = read_csv(DAILY_NEED_FILE)
    check_header(header, ["id", "min", "max"], DAILY_NEED_FILE)
    needs = []
    for line, row in enumerate(rows, start=2):
        if len(row) != 3:
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
            "name": " + ".join(nutrients[i][0] for i in ids),
            "unit": "/".join(dict.fromkeys(nutrients[i][1] for i in ids)),
            "min": _to_float(row[1], f"min at {where}") if row[1] else 0.0,
            "max": _to_float(row[2], f"max at {where}") if row[2] else None,
        })
    return needs


def daily_need_block():
    """Formats the daily need table for a prompt, with the nutrient names and units."""
    rows = [
        [", ".join(map(str, need["ids"])), need["name"], need["unit"], f"{need['min']:g}",
         "" if need["max"] is None else f"{need['max']:g}"]
        for need in load_daily_needs()
    ]
    return file_block(DAILY_NEED_FILE.name, rows_to_csv(["id", "name", "unit", "min", "max"], rows))


# ---------------------------------------------------------
# LLM answers
# ---------------------------------------------------------
def parse_food_nutrient_csv(text, known_fdc_ids):
    """Strictly validates a food_nutrient CSV answer and returns its data rows."""
    header, rows = _split_header(list(csv.reader(io.StringIO(extract_csv(text)))), "The clipboard CSV")
    check_header(header, FOOD_NUTRIENT_HEADER, "the clipboard")
    if not rows:
        raise ValueError("No data rows found in the clipboard CSV (only header).")

    seen = set()
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
    return rows


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
