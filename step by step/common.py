"""Shared helpers for the step by step scripts (see README.md).

Every script reads the clipboard and/or the DB files, then copies the next prompt to the clipboard.
Anything wrong raises: 0_run_all shows the error and offers to run the script again.

The menu is the list of the foods of a day. A food is a SR Legacy one (food.csv), or a manual one
(food_manual.csv). A manual food that has just been added is a new food (new_food.csv): its nutrients
(food_nutrient_manual.csv) are deduced from its ingredients (food_ingredient_manual.csv).
"""
import csv
import io
import json
import math
import os
import re
from contextlib import contextmanager
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
NEW_FOOD_FILE = DB_DIR / "new_food.csv"
MENU_FILE = DB_DIR / "menu.csv"
SUCCESSFUL_MENU_FILE = DB_DIR / "successful_menus.csv"
# The answers to the options of the menu, with the address of the user: not in git
MENU_OPTION_FILE = DB_DIR / "menu_options.json"

# The amount of a food is in grams, its nutrients being given for 100g. A supplement taken as a pill has no
# meaningful weight: its amount is a number of doses, its nutrients being given for one dose.
GRAM, DOSE = "g", "dose"
UNITS = (GRAM, DOSE)

# What the LLM writes instead of an fdc_id for a food that is in no food database
NEW = "new"
# What it writes as the only ingredient of a food that cannot be made from other foods
NONE = "none"

FOOD_HEADER = ["fdc_id", "description", "unit"]
MENU_HEADER = ["fdc_id", "description", "amount", "unit"]
# How the LLM writes the menu, then the food each row of the menu is, then the ingredients and the nutrients
MENU_ANSWER_HEADER = ["description", "amount", "unit"]
FOOD_LIST_HEADER = ["description", "fdc_id", "fdc_description"]
INGREDIENT_HEADER = ["fdc_id", "ingredient_fdc_id", "ingredient_description", "quantity"]
NUTRIENT_ANSWER_HEADER = ["fdc_id", "nutrient_id", "amount"]
FOOD_NUTRIENT_HEADER = [
    "id", "fdc_id", "nutrient_id", "amount", "data_points",
    "derivation_id", "min", "max", "median",
]

# Start of the prompt a check step gives back to the LLM when it finds an error itself
ERROR_PROMPT = "Your csv output is incorrect, write the whole corrected csv. The error is:"

MENU_RULES = f"""- One row per food eaten or drunk in the day, the water and the supplements too. A food is preferably a simple one, described in the state it is weighed in (raw, cooked, dry, ...), or else a dish.
- amount: the grams of the food for the whole day, with {GRAM} as unit. Convert the cups, spoons and pieces to grams. Only for a supplement taken as a pill or a capsule: the number of doses, with {DOSE} as unit.
- A food has only one row: sum its amounts when it is eaten several times in the day."""
MENU_NOTE = f"""Write the menu as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in MENU_ANSWER_HEADER)}
{MENU_RULES}"""
SEARCH_NOTE = """Use your web search tool to look into SR Legacy 2018 from fdc.nal.usda.gov (its food.csv file). Your memory of the IDs is not reliable: never write an fdc_id you did not read. A SR Legacy fdc_id is between 167512 and 175304, it is not a NDB number."""
# The options of the menu asked at step 1.0: (key, question, what the prompt says when it is chosen)
MENU_OPTIONS = [
    ("location", "Tell the LLM where you live", "I live at {address}: choose foods that are easy to find in the shops there."),
    ("cheap", "Must the menu be as cheap as possible", "The menu must be as cheap as possible."),
    (
        "eco",
        "Must the menu be as environmentally friendly as possible",
        "The menu must be as environmentally friendly as possible: low carbon and water footprint, foods that are local and in season when possible.",
    ),
    ("quick", "Must the menu be as quick to prepare as possible", "The menu must be as quick to prepare as possible."),
]
MENU_OPTION_INTRO = "The menu must also follow these wishes, the daily nutrient needs coming first:"
# For the prompts that correct a menu: the wishes alone are no reason to change it
MENU_OPTION_KEEP_INTRO = "The menu was made with these wishes. Do not correct it only for them, but follow them in what you change:"
NUTRIENT_ID_NOTE ="""When a row of daily_need_table.csv has several IDs (e.g. "1278, 1272"), the need is the sum of those nutrients: each of them must still have its own row with its single nutrient_id and its own amount. Never write a combined ID or a summed amount in the csv."""
NUTRIENT_UNIT_NOTE = f"""The amounts are for 100g of the food when its unit is {GRAM}, for one dose when its unit is {DOSE}, in the unit of the nutrient."""


def answer_note(header):
    """Returns the end of a check prompt: what the LLM must answer, the csv having those columns."""
    return (
        "If it is correct, only answer that it is correct, without any csv. If not, write the whole corrected "
        f"csv, as a text easy to copy with those columns:\n{','.join(f'"{col}"' for col in header)}"
    )


# ---------------------------------------------------------
# Clipboard
# ---------------------------------------------------------
def get_clipboard():
    """Returns the clipboard text with normalized line endings; raises if it is empty."""
    text = pyperclip.paste().replace("\r\n", "\n")
    if not text.strip():
        raise ValueError("Clipboard is empty or contains no text.")
    return text


# The last prompt given, for 0_run_all to copy it again
last_prompt = None


def set_clipboard(text):
    global last_prompt
    last_prompt = text
    pyperclip.copy(text)
    print("The new prompt has been copied to your clipboard.")


class AnswerError(ValueError):
    """The csv of the clipboard is wrong: the prompt that tells the LLM about it is in the clipboard."""


@contextmanager
def errors_to_llm(note=""):
    """Gives the error raised while reading the csv of the clipboard back to the LLM, instead of asking for a check."""
    try:
        yield
    except ValueError as e:
        set_clipboard(f"{ERROR_PROMPT}\n{e}" + (f"\n\n{note}" if note else ""))
        print("It tells the LLM about the error below: paste it in the discussion that gave the csv.")
        raise AnswerError(str(e)) from None


# ---------------------------------------------------------
# Menu options
# ---------------------------------------------------------
def load_menu_options():
    """Returns what was answered at step 1.0: whether each option is chosen, the address and the other wishes."""
    try:
        return json.loads(MENU_OPTION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ask_yes_no(question, last):
    while True:
        answer = input(f"  {question}? (y/n) [{'y' if last else 'n'}]: ").strip().lower()
        if answer in ("", "y", "n"):
            return last if not answer else answer == "y"
        print("  Answer y or n.")


def ask_menu_options():
    """Asks the user the options of the menu, the last answers being the default ones, and saves them."""
    options = load_menu_options()
    print("Options of the menu (Enter keeps the answer in brackets):")
    for key, question, _ in MENU_OPTIONS:
        options[key] = _ask_yes_no(question, bool(options.get(key)))
    # The address is only asked once: it is changed in the file
    while options["location"] and not options.get("address"):
        options["address"] = input("  Your address: ").strip()
    last = options.get("other", "")
    answer = input(f"  Anything else to ask for the menu? (text, - for nothing) [{last or '-'}]: ").strip()
    options["other"] = "" if answer == "-" else answer or last
    MENU_OPTION_FILE.write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8")


def menu_option_note(intro=MENU_OPTION_INTRO):
    """Returns the lines of a prompt that tell the wishes chosen at step 1.0, nothing when there is none."""
    options = load_menu_options()
    wishes = [
        text.format(address=options.get("address", ""))
        for key, _, text in MENU_OPTIONS
        if options.get(key) and (key != "location" or options.get("address"))
    ]
    if options.get("other"):
        wishes.append(options["other"])
    return "".join(f"{line}\n" for line in [intro, *(f"- {wish}" for wish in wishes)]) if wishes else ""


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


def parse_answer(text, required):
    """Returns the rows of the csv of an LLM answer as a list of (line, {column: value}).

    The columns may be in any order, and others may be there too: the LLM often gives back those of the table
    it was shown.
    """
    header, rows = _split_header(list(csv.reader(io.StringIO(extract_csv(text)))), "The clipboard CSV")
    columns = [col.lower() for col in header]
    if any(col not in columns for col in required):
        raise ValueError(f"CSV column mismatch in the clipboard!\nExpected: {required}\nFound:    {header}")
    if not rows:
        raise ValueError("No data rows found in the clipboard CSV (only header).")
    records = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(columns):
            raise ValueError(
                f"Malformed CSV at row {line}: expected {len(columns)} columns, but found {len(row)}.\nRow data: {row}"
            )
        records.append((line, dict(zip(columns, row))))
    return records


def to_int(value, what):
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid {what}: '{value}' is not an integer.") from None


def to_float(value, what):
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid {what}: '{value}' is not a number.") from None


# ---------------------------------------------------------
# Foods
# ---------------------------------------------------------
def normalize(description):
    """Returns a food description without its case and spacing, to compare descriptions."""
    return " ".join(description.lower().split())


def _load_foods(path):
    """Returns the foods of a file as a list of (fdc_id, description, unit); none if it does not exist yet."""
    if not path.exists():
        return []
    header, rows = read_csv(path)
    check_header(header, FOOD_HEADER, path)
    foods = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(header) or not row[1] or row[2] not in UNITS:
            raise ValueError(f"Malformed row {line} in {path}: {row}")
        foods.append((to_int(row[0], f"fdc_id at row {line} of {path}"), row[1], row[2]))
    return foods


def load_manual_foods():
    """Returns the manual foods as a list of (fdc_id, description, unit)."""
    return _load_foods(FOOD_MANUAL_FILE)


def load_new_foods():
    """Returns the new foods, the manual foods whose nutrients are being found, as a list of (fdc_id, description, unit)."""
    return _load_foods(NEW_FOOD_FILE)


def save_new_foods(foods):
    write_csv(NEW_FOOD_FILE, FOOD_HEADER, foods)


def load_sr_legacy_foods():
    """Returns the SR Legacy foods as {fdc_id: description}."""
    header, rows = read_csv(FOOD_FILE)
    id_col, description_col = header.index("fdc_id"), header.index("description")
    return {int(row[id_col]): row[description_col] for row in rows}


def load_all_foods():
    """Returns the SR Legacy and the manual foods as {fdc_id: description}."""
    foods = load_sr_legacy_foods()
    foods.update((fdc_id, description) for fdc_id, description, _ in load_manual_foods())
    return foods


def load_food_units():
    """Returns the unit of the manual foods as {fdc_id: unit}. A SR Legacy food is always in grams."""
    return {fdc_id: unit for fdc_id, _, unit in load_manual_foods()}


def register_manual_foods(wanted):
    """Adds the (description, unit) foods that food_manual.csv does not have yet, with the smallest free IDs.

    Returns the manual foods as {normalized description: fdc_id}.
    """
    foods = load_manual_foods()
    known = {normalize(description): (fdc_id, unit) for fdc_id, description, unit in foods}
    # An ID that still has nutrients or ingredients would give them to the new food
    used = (
        set(load_sr_legacy_foods()) | {fdc_id for fdc_id, _, _ in foods}
        | manual_nutrient_food_ids() | set(load_ingredients())
    )
    added = []
    current_id = 1
    for description, unit in wanted:
        key = normalize(description)
        if key in known:
            if known[key][1] != unit:
                raise ValueError(
                    f"'{description}' is already the food {known[key][0]} of {FOOD_MANUAL_FILE.name}, whose amount "
                    f"is in {known[key][1]}, not in {unit}."
                )
            continue
        while current_id in used:
            current_id += 1
        foods.append((current_id, description, unit))
        known[key] = (current_id, unit)
        used.add(current_id)
        added.append(description)
    if added:
        write_csv(FOOD_MANUAL_FILE, FOOD_HEADER, foods)
        print(f"Added to '{FOOD_MANUAL_FILE}': {', '.join(added)}.")
    return {key: fdc_id for key, (fdc_id, _) in known.items()}


def food_manual_block():
    return file_block(FOOD_MANUAL_FILE.name, rows_to_csv(FOOD_HEADER, load_manual_foods()))


def new_food_block(foods):
    """Formats (fdc_id, description, unit) new foods for a prompt."""
    return file_block(f"{NEW_FOOD_FILE.name} (the new foods)", rows_to_csv(FOOD_HEADER, foods))


# ---------------------------------------------------------
# Food search
# ---------------------------------------------------------
def _words(description):
    """Returns the words of a food description, without their plural, to compare descriptions."""
    return {word.rstrip("s") for word in re.findall(r"[a-z]+", description.lower()) if len(word) > 2}


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


def check_food_ids(claims, foods):
    """Raises if an ID given by the LLM is not the food it says.

    claims is a list of (line, fdc_id, description) as the LLM wrote them, foods ({fdc_id: description}) the
    real foods. All the wrong ones are given at once, so that the LLM corrects them in one go.
    """
    errors, searched = [], []
    for line, fdc_id, description in claims:
        if not fdc_id.isdigit() or int(fdc_id) not in foods:
            errors.append(
                f"- row {line}: the fdc_id '{fdc_id}' exists neither in SR Legacy 2018 nor in {FOOD_MANUAL_FILE.name}"
            )
        elif normalize(description) != normalize(foods[int(fdc_id)]):
            errors.append(f'- row {line}: the fdc_id {fdc_id} is "{foods[int(fdc_id)]}", not "{description}"')
        else:
            continue
        if description:
            searched.append(description)
    if not errors:
        return
    message = (
        "Those fdc_id are not the foods you describe:\n" + "\n".join(errors)
        + "\nWhen the real description of the fdc_id is the food you meant, write it exactly as it is."
    )
    if searched:
        # Its memory of the IDs is not reliable: give it the real ones to choose from
        message += (
            " Otherwise do not guess another ID: take it, with its description, from those foods, searched from "
            f"your descriptions:\n{candidates_block(searched, foods)}"
        )
    raise ValueError(message)


# ---------------------------------------------------------
# Menu
# ---------------------------------------------------------
def load_menu():
    """Returns the rows of menu.csv, as [fdc_id, description, amount, unit].

    fdc_id is empty for a food that is not identified yet, NEW for a food that is in no food database.
    """
    if not MENU_FILE.exists():
        raise ValueError(f"{MENU_FILE.name} does not exist yet: run step 1.5 first.")
    header, rows = read_csv(MENU_FILE)
    check_header(header, MENU_HEADER, MENU_FILE)
    if not rows:
        raise ValueError(f"{MENU_FILE.name} has no food: run step 1.5 first.")
    # A manual food may have been removed since the menu was saved: its row is to identify again
    foods = load_all_foods()
    for row in rows:
        if row[0].isdigit() and int(row[0]) not in foods:
            print(f"The food {row[0]} of '{row[1]}' does not exist anymore: it is not identified anymore.")
            row[0] = ""
    return rows


def load_identified_menu():
    """Returns the menu as a list of (fdc_id, amount, unit); raises while a food has no ID."""
    rows = load_menu()
    without_id = [description for fdc_id, description, _, _ in rows if not fdc_id.isdigit()]
    if without_id:
        raise ValueError(
            f"Those foods of {MENU_FILE.name} have no ID yet, finish steps 2.5 and 3.0 first: {', '.join(without_id)}"
        )
    return [(int(fdc_id), float(amount), unit) for fdc_id, _, amount, unit in rows]


def save_menu(rows):
    """Writes the whole menu (see load_menu) to menu.csv."""
    write_csv(MENU_FILE, MENU_HEADER, rows)
    print(f"Successfully wrote the {len(rows)} foods of the menu to '{MENU_FILE}'.")


def save_successful_menu(rows, date):
    """Adds the menu (see load_menu) to successful_menus.csv, the menus that satisfy the daily needs.

    Each of its rows starts with the number of the menu and its date. A menu that is already there is not added again.
    """
    header = ["menu", "date", *MENU_HEADER]
    existing = []
    if SUCCESSFUL_MENU_FILE.exists():
        found, existing = read_csv(SUCCESSFUL_MENU_FILE)
        check_header(found, header, SUCCESSFUL_MENU_FILE)
    menus = {}
    for row in existing:
        menus.setdefault(int(row[0]), set()).add((row[2], row[4], row[5]))
    same = [number for number, foods in menus.items() if foods == {(row[0], row[2], row[3]) for row in rows}]
    if same:
        print(f"This menu is already the menu {same[0]} of '{SUCCESSFUL_MENU_FILE}'.")
        return
    number = max(menus, default=0) + 1
    write_csv(SUCCESSFUL_MENU_FILE, header, existing + [[number, date, *row] for row in rows])
    print(f"Saved as the menu {number} of '{SUCCESSFUL_MENU_FILE}'.")


def menu_block(rows, foods=None):
    """Formats the menu (see load_menu) for a prompt.

    With foods ({fdc_id: description}), each row also has its ID and the real description of this ID.
    """
    header = MENU_ANSWER_HEADER
    table = [row[1:] for row in rows]
    if foods is not None:
        header = header + ["fdc_id", "fdc_description"]
        table = [
            [*row[1:], row[0], foods[int(row[0])] if row[0].isdigit() else ""] for row in rows
        ]
    return file_block(
        f"{MENU_FILE.name} (amount: for the whole day, in the unit of the row)", rows_to_csv(header, table)
    )


def parse_menu_csv(text):
    """Strictly validates a menu CSV answer and returns its rows (see load_menu), without any ID."""
    rows = []
    seen = set()
    for line, record in parse_answer(text, MENU_ANSWER_HEADER):
        description = record["description"]
        if not description:
            raise ValueError(f"Row {line} has no description.")
        if normalize(description) in seen:
            raise ValueError(f"'{description}' is given twice (row {line}): a food has only one row, sum its amounts.")
        seen.add(normalize(description))
        amount = to_float(record["amount"], f"amount at row {line}")
        unit = record["unit"].lower()
        if amount <= 0:
            raise ValueError(f"Invalid amount {amount} at row {line}.")
        if unit not in UNITS:
            raise ValueError(f"Invalid unit '{record['unit']}' at row {line}: it must be {GRAM} or {DOSE}.")
        rows.append(["", description, f"{amount:g}", unit])
    return rows


# ---------------------------------------------------------
# Ingredients of the manual foods
# ---------------------------------------------------------
def load_ingredients():
    """Returns the ingredients of the manual foods as {fdc_id: [(ingredient_fdc_id, quantity)]}.

    The list is empty for a food that cannot be made from other foods (NONE).
    """
    if not FOOD_INGREDIENT_MANUAL_FILE.exists():
        return {}
    header, rows = read_csv(FOOD_INGREDIENT_MANUAL_FILE)
    check_header(header, INGREDIENT_HEADER, FOOD_INGREDIENT_MANUAL_FILE)
    ingredients = {}
    for line, row in enumerate(rows, start=2):
        try:
            of_food = ingredients.setdefault(int(row[0]), [])
            if row[1] != NONE:
                of_food.append((int(row[1]), float(row[3])))
        except (IndexError, ValueError) as e:
            raise ValueError(f"Malformed row {line} in {FOOD_INGREDIENT_MANUAL_FILE}: {row}") from e
    return ingredients


def save_ingredients(rows):
    """Writes [fdc_id, ingredient_fdc_id, ingredient_description, quantity] rows to food_ingredient_manual.csv,
    replacing the rows of the same foods."""
    existing = []
    if FOOD_INGREDIENT_MANUAL_FILE.exists():
        header, existing = read_csv(FOOD_INGREDIENT_MANUAL_FILE)
        check_header(header, INGREDIENT_HEADER, FOOD_INGREDIENT_MANUAL_FILE)
    # A food given again is replaced as a whole, so that none of its old ingredients remains
    given = {str(row[0]) for row in rows}
    write_csv(FOOD_INGREDIENT_MANUAL_FILE, INGREDIENT_HEADER, [row for row in existing if row[0] not in given] + rows)
    print(f"Successfully wrote the ingredients of {len(given)} foods to '{FOOD_INGREDIENT_MANUAL_FILE}'.")


def ingredient_block(fdc_ids, foods):
    """Formats the ingredients of those foods for a prompt, foods ({fdc_id: description}) describing them."""
    ingredients = load_ingredients()
    rows = []
    for fdc_id in fdc_ids:
        if fdc_id in ingredients:
            rows += [
                [fdc_id, ingredient_id, foods[ingredient_id], f"{quantity:g}"]
                for ingredient_id, quantity in ingredients[fdc_id]
            ] or [[fdc_id, NONE, "", ""]]
    return file_block(
        f"{FOOD_INGREDIENT_MANUAL_FILE.name} (the ingredients of the new foods)", rows_to_csv(INGREDIENT_HEADER, rows)
    )


# ---------------------------------------------------------
# Nutrients of the foods
# ---------------------------------------------------------
def _read_manual_nutrients():
    """Returns the data rows of food_nutrient_manual.csv; none if the file does not exist yet."""
    if not FOOD_NUTRIENT_MANUAL_FILE.exists():
        return []
    header, rows = read_csv(FOOD_NUTRIENT_MANUAL_FILE)
    check_header(header, FOOD_NUTRIENT_HEADER, FOOD_NUTRIENT_MANUAL_FILE)
    return rows


def manual_nutrient_food_ids():
    """Returns the IDs of the foods that have nutrients in food_nutrient_manual.csv."""
    return {int(row[1]) for row in _read_manual_nutrients()}


def load_manual_nutrients():
    """Returns the nutrients of food_nutrient_manual.csv as {fdc_id: {nutrient_id: amount}}."""
    nutrients = {}
    for row in _read_manual_nutrients():
        nutrients.setdefault(int(row[1]), {})[int(row[2])] = float(row[3])
    return nutrients


def save_to_nutrient_manual(rows, replace_foods=False):
    """Writes (fdc_id, nutrient_id, amount) rows to food_nutrient_manual.csv, replacing those of the same nutrient
    of the same food. With replace_foods, the foods given are replaced as a whole: none of their old rows remains.
    """
    existing = _read_manual_nutrients()
    given_foods = {str(fdc_id) for fdc_id, _, _ in rows}
    given = {(str(fdc_id), str(nutrient_id)) for fdc_id, nutrient_id, _ in rows}
    kept = [
        row for row in existing
        if (row[1], row[2]) not in given and not (replace_foods and row[1] in given_foods)
    ]
    if len(kept) < len(existing):
        print(f"Replacing {len(existing) - len(kept)} existing nutrient records.")

    # The IDs must stay unique: number the new rows after the last one of the file
    next_id = max((int(row[0]) for row in existing), default=49999) + 1
    new = [
        [next_id + i, fdc_id, nutrient_id, f"{amount:.6g}", "", "", "", "", ""]
        for i, (fdc_id, nutrient_id, amount) in enumerate(rows)
    ]
    write_csv(FOOD_NUTRIENT_MANUAL_FILE, FOOD_NUTRIENT_HEADER, kept + new)
    print(f"Successfully wrote {len(new)} nutrient records to '{FOOD_NUTRIENT_MANUAL_FILE}'.")


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


def compute_nutrients(fdc_ids):
    """Deduces the nutrients of those foods from their ingredients, and writes them to food_nutrient_manual.csv.

    Returns the foods that were computed. The others cannot be made from other foods, or wait for the nutrients
    of one of their ingredients.
    """
    ingredients = load_ingredients()
    pending = [fdc_id for fdc_id in dict.fromkeys(fdc_ids) if ingredients.get(fdc_id)]
    if not pending:
        return []
    nutrients = load_food_nutrients({ingredient_id for fdc_id in pending for ingredient_id, _ in ingredients[fdc_id]})
    units = load_food_units()
    needed = needed_nutrient_ids()

    rows = []
    computed = []
    progress = True
    while pending and progress:
        progress = False
        for fdc_id in list(pending):
            # An ingredient that is one of those foods is computed first
            if any(i in pending or i not in nutrients for i, _ in ingredients[fdc_id]):
                continue
            nutrients[fdc_id] = {}
            for nutrient_id in needed:
                # The nutrients are given for 100g of an ingredient, or for one dose of a supplement
                parts = [
                    (quantity if units.get(i) == DOSE else quantity / 100, nutrients[i].get(nutrient_id))
                    for i, quantity in ingredients[fdc_id]
                ]
                # Without data for any ingredient, the nutrient is left out rather than said to be 0: step 4.0 asks for it
                if any(amount is not None for _, amount in parts):
                    nutrients[fdc_id][nutrient_id] = sum(share * (amount or 0) for share, amount in parts)
            rows += [(fdc_id, nutrient_id, amount) for nutrient_id, amount in nutrients[fdc_id].items()]
            computed.append(fdc_id)
            pending.remove(fdc_id)
            progress = True
    if rows:
        save_to_nutrient_manual(rows, replace_foods=True)
    return computed


def nutrient_block(fdc_ids):
    """Formats the nutrients that food_nutrient_manual.csv has for those foods for a prompt, with their names and units."""
    names = load_nutrients()
    nutrients = load_manual_nutrients()
    rows = [
        [fdc_id, nutrient_id, *names[nutrient_id], f"{nutrients[fdc_id][nutrient_id]:g}"]
        for fdc_id in fdc_ids
        for nutrient_id in needed_nutrient_ids()
        if nutrient_id in nutrients.get(fdc_id, {})
    ]
    return file_block(
        f"{FOOD_NUTRIENT_MANUAL_FILE.name} (the nutrients of the new foods)",
        rows_to_csv(["fdc_id", "nutrient_id", "name", "unit", "amount"], rows),
    )


# ---------------------------------------------------------
# daily_need_table.csv
# ---------------------------------------------------------
def load_nutrients():
    """Returns the SR Legacy nutrients as {id: (name, unit)}."""
    header, rows = read_csv(NUTRIENT_FILE)
    id_col, name_col, unit_col = (header.index(col) for col in ("id", "name", "unit_name"))
    return {to_int(row[id_col], f"id in {NUTRIENT_FILE}"): (row[name_col], row[unit_col]) for row in rows}


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
        ids = [to_int(i.strip(), f"nutrient id at {where}") for i in row[0].split(",") if i.strip()]
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
            "min": to_float(row[2], f"min at {where}") if row[2] else 0.0,
            "max": to_float(row[3], f"max at {where}") if row[3] else None,
        })
    return needs


def needed_nutrient_ids():
    """Returns the IDs of the nutrients of daily_need_table.csv, in its order."""
    return [nutrient_id for need in load_daily_needs() for nutrient_id in need["ids"]]


def daily_need_block():
    """Formats the daily need table for a prompt, with the nutrient units."""
    rows = [
        [", ".join(map(str, need["ids"])), need["name"], need["unit"], f"{need['min']:g}",
         "" if need["max"] is None else f"{need['max']:g}"]
        for need in load_daily_needs()
    ]
    return file_block(
        f"{DAILY_NEED_FILE.name} (min and max: for the whole day, an empty max meaning no limit)",
        rows_to_csv(["id", "name", "unit", "min", "max"], rows),
    )
