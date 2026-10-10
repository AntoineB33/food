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
from datetime import datetime
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
# The menu as a text, meal by meal: menu.csv is written from it
MENU_DESCRIPTION_FILE = DB_DIR / "menu_description.txt"
# The menu with the amounts this text has, while menu.csv has others that step 6.0 computed and the text is not
# written again yet: a menu is not saved as successful with a text that is not its own. Not in git
MENU_TEXT_AMOUNT_FILE = DB_DIR / "menu_text_amounts.csv"
SUCCESSFUL_MENU_FILE = DB_DIR / "successful_menus.csv"
# The text of each menu of successful_menus.csv, in a file named after its number
SUCCESSFUL_MENU_DESCRIPTION_DIR = DB_DIR / "successful_menu_descriptions"
# The real products the user buys, each one being a food of food.csv or of food_manual.csv, the nutrients their
# label gives, and the product each food of the menu is counted as
PRODUCT_FILE = DB_DIR / "product.csv"
PRODUCT_NUTRIENT_FILE = DB_DIR / "product_nutrient.csv"
MENU_PRODUCT_FILE = DB_DIR / "menu_product.csv"
# The answers to the options of the menu, with the address of the user: not in git
MENU_OPTION_FILE = DB_DIR / "menu_options.json"
# The goals and tips of the user, a free text: a menu is made, corrected and judged with them
MENU_TIPS_FILE = DB_DIR / "menu_tips.txt"
# The least and the most of a food that is realistic and safe in a day, for the foods an LLM refused an amount of:
# the amounts that step 6.0 computes stay within them, in every menu
FOOD_LIMIT_FILE = DB_DIR / "food_limit.csv"
# The foods the user is willing to buy and eat: step 0.0 computes a menu from them. Each one has a max in
# food_limit.csv. The foods of a menu that satisfies the daily needs are added to it
FOOD_POOL_FILE = DB_DIR / "food_pool.csv"
# What was printed, the prompts and the answers of the LLM, in one file per menu made with 0_run_all. The prompts
# tell the address of the user: not in git
HISTORY_DIR = DB_DIR / "history"

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
# options: the keys of the options (see MENU_OPTIONS) the menu was made with, other: its other wishes,
# needs: the changes of the daily needs it was made with (see need_changes_cell),
# product_id: the product the food was counted as, empty when it was counted as the generic food
SUCCESSFUL_MENU_HEADER = ["menu", "date", *MENU_HEADER, "options", "other", "needs", "product_id"]
# How the LLM writes the menu, then the food each row of the menu is, then the ingredients and the nutrients
MENU_ANSWER_HEADER = ["description", "amount", "unit"]
FOOD_LIST_HEADER = ["description", "fdc_id", "fdc_description"]
INGREDIENT_HEADER = ["fdc_id", "ingredient_fdc_id", "ingredient_description", "quantity"]
NUTRIENT_ANSWER_HEADER = ["fdc_id", "nutrient_id", "amount"]
# price: in euros for package_amount, which is in the unit of the food. eco: from A (the best) to E.
# source: where the information comes from, ON_SITE when the user read it on the product
PRODUCT_HEADER = ["product_id", "fdc_id", "description", "shop", "price", "package_amount", "eco", "source", "date"]
PRODUCT_NUTRIENT_HEADER = ["product_id", "nutrient_id", "amount", "source"]
MENU_PRODUCT_HEADER = ["fdc_id", "product_id"]
# How the LLM writes the products, then their nutrients
PRODUCT_ANSWER_HEADER = ["fdc_id", "product", "shop", "price", "package_amount", "eco", "source"]
PRODUCT_NUTRIENT_ANSWER_HEADER = ["product", "nutrient_id", "amount", "source"]
ON_SITE = "on site"
# What an answer to the prompt of the report corrects (see answer_kind)
MENU_ANSWER, PRODUCT_ANSWER, LIMIT_ANSWER = "menu", "products", "limits"
# min, max: in the unit of the food, for a day, empty without limit
FOOD_LIMIT_HEADER = ["fdc_id", "description", "min", "max"]
FOOD_POOL_HEADER = ["fdc_id", "description"]
# How the LLM writes the foods it proposes for the pool: max is the most of the food in a day
POOL_ANSWER_HEADER = ["description", "fdc_id", "fdc_description", "max"]
# How the LLM writes the limits of the foods it refuses the amount of
LIMIT_ANSWER_HEADER = ["description", "min", "max"]
LIMIT_NOTE = f"""as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in LIMIT_ANSWER_HEADER)}
- description: the one of the food in the table of the menu, unchanged.
- min, max: the least and the most of this food that is realistic and safe to have in a day, in the unit of its row, one of the two being empty when there is no limit on that side.
- The amounts are computed again within them: give the widest limits you accept, not the amount you prefer."""
ECO_LEVELS = "ABCDE"
# The menu counts on a food for a nutrient when it brings at least this share of its total of the day: with less,
# the product bought changes little
SHARE = 0.2
DEPENDENCE_HEADER = [
    "fdc_id", "description", "nutrient_id", "nutrient", "unit",
    "amount_in_food", "amount_in_day", "total_of_the_day", "share_percent", "needed",
]
FOOD_NUTRIENT_HEADER = [
    "id", "fdc_id", "nutrient_id", "amount", "data_points",
    "derivation_id", "min", "max", "median",
]

# Start of the prompt a check step gives back to the LLM when it finds an error itself
ERROR_PROMPT = "Your csv output is incorrect, write the whole corrected csv. The error is:"

MENU_RULES = f"""- One row per food eaten or drunk in the day, the water and the supplements too. A food is preferably a simple one, described in the state it is weighed in (raw, cooked, dry, ...), or else a dish.
- amount: the grams of the food for the whole day, with {GRAM} as unit. Convert the cups, spoons and pieces to grams. Only for a supplement taken as a pill or a capsule: the number of doses, with {DOSE} as unit.
- A food has only one row: sum its amounts when it is eaten several times in the day."""
MENU_NOTE = f"""First write the menu as a text: each meal of the day, with its foods and the grams of each one (with the cups, spoons or pieces too when it helps). Then write it again as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in MENU_ANSWER_HEADER)}
{MENU_RULES}
- The text and the csv must say the same: every food of the text is in the csv with the sum of its amounts, and the csv has no other food."""
SEARCH_NOTE = """Use your web search tool to look into SR Legacy 2018 from fdc.nal.usda.gov (its food.csv file). Your memory of the IDs is not reliable: never write an fdc_id you did not read. A SR Legacy fdc_id is between 167512 and 175304, it is not a NDB number."""
POOL_NOTE = f"""Write them as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in POOL_ANSWER_HEADER)}
- description: the food as you would name it.
- fdc_id, fdc_description: its ID in SR Legacy 2018 or in food_manual.csv, and its exact description there, in the state it is weighed in (raw, cooked, dry, ...). They are checked against the databases.
- max: the most of this food that is realistic and safe to have every day, in grams, or in doses for a food of food_manual.csv whose unit is {DOSE}.
- Only vegan foods that are in one of the two databases, and that food_pool.csv does not have yet.
{SEARCH_NOTE}"""
# The options of the menu asked at step 1.0: (key, question, what the prompt says when it is chosen, what a menu
# made with it is said to be made)
MENU_OPTIONS = [
    (
        "location",
        "Tell the LLM where you live",
        "I live at {address}: choose foods that are easy to find in the shops there.",
        "for where you live",
    ),
    (
        "cheap",
        "Must the menu be as cheap as possible",
        "The menu must be as cheap as possible.",
        "to be as cheap as possible",
    ),
    (
        "eco",
        "Must the menu be as environmentally friendly as possible",
        "The menu must be as environmentally friendly as possible: low carbon and water footprint, foods that are local and in season when possible.",
        "to be as environmentally friendly as possible",
    ),
    (
        "quick",
        "Must the menu be as quick to prepare as possible",
        "The menu must be as quick to prepare as possible.",
        "to be as quick to prepare as possible",
    ),
]
MENU_OPTION_INTRO = "The menu must also follow these wishes, the daily nutrient needs coming first:"
# For the prompts that correct a menu: the wishes alone are no reason to change it
MENU_OPTION_KEEP_INTRO = "The menu was made with these wishes. Do not correct it only for them, but follow them in what you change:"
# The foods asked at step 1.0 are not wishes: a menu that does not follow them is wrong
MENU_INCLUDE_INTRO = "The menu must have each of these foods, whatever the amount. In the csv, the row of each one has exactly this description:"
MENU_EXCLUDE_INTRO = "The menu must have none of these foods, under any description:"
NUTRIENT_ID_NOTE ="""When a row of daily_need_table.csv has several IDs (e.g. "1278, 1272"), the need is the sum of those nutrients: each of them must still have its own row with its single nutrient_id and its own amount. Never write a combined ID or a summed amount in the csv."""
NUTRIENT_UNIT_NOTE = f"""The amounts are for 100g of the food when its unit is {GRAM}, for one dose when its unit is {DOSE}, in the unit of the nutrient."""
SOURCE_NOTE = f"""the website you read it on, or estimate when it is your own knowledge. {ON_SITE} is only for what I told you I read myself on the product."""
DEPENDENCE_NOTE = f"""menu_dependence.csv tells the nutrients the menu counts on each food for: the ones it brings at least {SHARE:.0%} of the total of the day of. amount_in_food: what the food is counted with, for 100g of it, or for one dose when its unit is {DOSE}. amount_in_day: what it brings with its amount of the menu. needed: yes when the day would be under its minimum without this food."""
PRODUCT_NUTRIENT_NOTE = f"""as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in PRODUCT_NUTRIENT_ANSWER_HEADER)}
- product: the product_id of a product of product.csv, or the description of a product of the first table.
- nutrient_id, amount: a nutrient of daily_need_table.csv, and its amount in the product. {NUTRIENT_UNIT_NOTE} The sodium of a product is the salt of its label divided by 2.5.
- Only the nutrients that the label or the page of the product gives: the others are taken from its generic food.
- source: where the number comes from: {SOURCE_NOTE}
- {NUTRIENT_ID_NOTE}"""
PRODUCT_NOTE = f"""Write two tables, each one as a text easy to copy in a csv format. The first one is the products, with those columns:
{",".join(f'"{col}"' for col in PRODUCT_ANSWER_HEADER)}
- fdc_id: the food of the menu that the product is.
- product: its brand and its name, as specific as it is useful to be and not more: the name is enough for a fresh vegetable, but the kind or the brand must be told when the nutrients the menu counts on depend on it.
- shop: where and how to buy it: the shop and its town, or the website.
- price: in euros, for the package. package_amount: what the package holds, in grams when the unit of the food is {GRAM}, in doses when it is {DOSE}. Both empty when you do not know them.
- eco: how environmentally friendly the product is, from {ECO_LEVELS[0]} (the best) to {ECO_LEVELS[-1]}, empty when you cannot tell.
- source: where the information comes from: {SOURCE_NOTE}
The second one is the nutrients of the products, {PRODUCT_NUTRIENT_NOTE}
- A product whose label gives nothing has no row in this second table."""


def answer_note(header):
    """Returns the end of a check prompt: what the LLM must answer, the csv having those columns."""
    return (
        "If it is correct, only answer that it is correct, without any csv. If not, write the whole corrected "
        f"csv, as a text easy to copy with those columns:\n{','.join(f'"{col}"' for col in header)}"
    )


# ---------------------------------------------------------
# Clipboard
# ---------------------------------------------------------
# The file of HISTORY_DIR of the menu being made: 0_run_all chooses it, a script that is run alone keeps no history
history_file = None


def write_history(text):
    """Adds a text to the history of the menu being made, when one is kept."""
    if history_file:
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(text)


def write_history_block(title, text):
    """Adds a prompt or an answer of the LLM to the history, between two lines that tell what it is."""
    write_history(
        f"\n{'<' * 20} {title} ({datetime.now():%H:%M:%S})\n{text.strip()}\n{'>' * 20} END OF THE {title}\n\n"
    )


def get_clipboard():
    """Returns the clipboard text with normalized line endings; raises if it is empty."""
    text = pyperclip.paste().replace("\r\n", "\n")
    if not text.strip():
        raise ValueError("Clipboard is empty or contains no text.")
    write_history_block("ANSWER OF THE LLM, READ FROM THE CLIPBOARD", text)
    return text


# The last prompt given, for 0_run_all to copy it again
last_prompt = None
# Whether it is the prompt that reviews a menu that satisfies the daily needs (see review_prompt)
last_prompt_is_review = False


def set_clipboard(text, review=False):
    global last_prompt, last_prompt_is_review
    last_prompt = text
    last_prompt_is_review = review
    pyperclip.copy(text)
    write_history_block("PROMPT, COPIED TO THE CLIPBOARD", text)
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


def ask_yes_no(question, last):
    while True:
        answer = input(f"  {question}? (y/n) [{'y' if last else 'n'}]: ").strip().lower()
        if answer in ("", "y", "n"):
            return last if not answer else answer == "y"
        print("  Answer y or n.")


def ask_menu_options():
    """Asks the user the options of the menu, the last answers being the default ones, and saves them."""
    options = load_menu_options()
    print("Options of the menu (Enter keeps the answer in brackets):")
    for key, question, _, _ in MENU_OPTIONS:
        options[key] = ask_yes_no(question, bool(options.get(key)))
    # The address is only asked once: it is changed in the file
    while options["location"] and not options.get("address"):
        options["address"] = input("  Your address: ").strip()
    last = options.get("other", "")
    answer = input(f"  Anything else to ask for the menu? (text, - for nothing) [{last or '-'}]: ").strip()
    options["other"] = "" if answer == "-" else answer or last
    foods = load_all_foods()
    include, exclude = options.get("include", []), options.get("exclude", [])
    options["include"] = ask_menu_foods("Foods the menu must have", include, exclude, foods)
    options["exclude"] = ask_menu_foods("Foods the menu must not have", exclude, options["include"], foods)
    options["needs"] = ask_need_changes(options.get("needs", []))
    MENU_OPTION_FILE.write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8")


def ask_menu_foods(question, kept, opposite, foods):
    """Asks the foods the menu must have, or must not have, and returns them as a list of [fdc_id, description].

    kept are the ones answered last, which stay unless the user removes them all. A food is typed as its fdc_id
    then its description, which must be the one of this ID in foods ({fdc_id: description}). A food that is added
    is removed from opposite, the other list.
    """
    # A manual food may have been removed or renamed since
    chosen = [
        [fdc_id, description] for fdc_id, description in kept
        if normalize(foods.get(fdc_id, "")) == normalize(description)
    ]
    print(f"  {question}: {'; '.join(f'{description} ({fdc_id})' for fdc_id, description in chosen) or 'none'}")
    while True:
        answer = input("    Add one, as its fdc_id then its description (Enter when done, - to remove them all): ").strip()
        if not answer:
            return chosen
        if answer == "-":
            chosen.clear()
            print("    None anymore.")
            continue
        match = re.fullmatch(r"(\d+)[\s,;:]+(.+)", answer)
        if not match:
            print("    Write the fdc_id, then the description, as in: 172430 Peanuts, all types, raw")
            continue
        fdc_id, description = int(match[1]), match[2].strip().strip('"')
        if fdc_id not in foods:
            error = f"The fdc_id {fdc_id} exists neither in SR Legacy 2018 nor in {FOOD_MANUAL_FILE.name}."
        elif normalize(description) != normalize(foods[fdc_id]):
            error = f'The fdc_id {fdc_id} is "{foods[fdc_id]}", not "{description}".'
        else:
            if all(fdc_id != chosen_id for chosen_id, _ in chosen):
                chosen.append([fdc_id, foods[fdc_id]])
            if any(fdc_id == other_id for other_id, _ in opposite):
                opposite[:] = [food for food in opposite if food[0] != fdc_id]
                print("    It is removed from the other list.")
            print(f"    Added: {foods[fdc_id]}")
            continue
        print(f"    {error} Not added. The closest foods to this description:")
        closest = food_candidates([description], foods)[description]
        print("\n".join(f"      {found_id} {found}" for found_id, found in closest) or "      nothing found")


def need_change_text(need, minimum, maximum):
    """Says what a change makes of the min and the max of a row of the daily needs (see load_daily_needs)."""
    def limit(value):
        return "no limit" if value is None else f"{value:g}"

    parts = [
        f"{what} {limit(old)} -> {limit(new)}"
        for what, old, new in (("min", need["min"], minimum), ("max", need["max"], maximum)) if old != new
    ]
    # The table may have been changed to it since
    return f"{need['name']} ({need['unit']}): " + (", ".join(parts) or f"min {limit(minimum)}, max {limit(maximum)}")


def ask_need_changes(kept):
    """Asks the changes of the rows of daily_need_table.csv, and returns them as a list of {ids, min, max, on}.

    The table itself is not changed: a change replaces the min and the max of its row while it is on. kept are
    the changes made before: each one is asked again, the last answer being the default one. A new one is typed as
    the whole row of the csv of the table, with its new min and max.
    """
    # The rows as the table has them, without any change. A row without nutrient id is not computed
    by_ids = {tuple(need["ids"]): need for need in load_daily_needs({}) if need["ids"]}
    example = 'Write the whole row as in the csv, with its id, its name, its min and its max, as in: 1003,Protein,120,150'

    print(f"  Changes of {DAILY_NEED_FILE.name}:{'' if kept else ' none'}")
    changes = []
    for change in kept:
        # A row may have been removed from the table since
        need = by_ids.get(tuple(change["ids"]))
        if need:
            text = need_change_text(need, change["min"], change["max"])
            changes.append({**change, "on": ask_yes_no(f"  Change {text}", change["on"])})
    while True:
        answer = input(
            "    Change a row, as the whole row of the csv with its new min and max (Enter when done, - to remove "
            "them all): "
        ).strip()
        if not answer:
            return changes
        if answer == "-":
            changes.clear()
            print("    None anymore.")
            continue
        try:
            cells = [cell.strip() for cell in next(csv.reader([answer]), [])]
        except csv.Error:
            cells = []
        if len(cells) < 4 or not re.fullmatch(r"\d+(\s*,\s*\d+)*", cells[0]):
            print(f"    {example}")
            continue
        # A name typed without its quotes is split at its commas
        ids, name, minimum, maximum = cells[0], ", ".join(cells[1:-2]), *cells[-2:]
        need = by_ids.get(tuple(int(nutrient_id) for nutrient_id in ids.split(",")))
        if need is None:
            print(f"    No row of {DAILY_NEED_FILE.name} has the id {ids}. Not changed.")
            continue
        if normalize(name) != normalize(need["name"]):
            print(f'    The row {ids} is "{need["name"]}", not "{name}". Not changed.')
            continue
        try:
            # As in the table, an empty min is 0 and an empty max is no limit
            minimum = float(minimum) if minimum else 0.0
            maximum = float(maximum) if maximum else None
        except ValueError:
            print("    The min and the max are numbers, the max being empty for no limit. Not changed.")
            continue
        if not 0 <= minimum < math.inf or (maximum is not None and not minimum <= maximum < math.inf):
            print("    The min cannot be negative, and the max cannot be under the min. Not changed.")
            continue
        was_changed = any(tuple(change["ids"]) == tuple(need["ids"]) for change in changes)
        changes[:] = [change for change in changes if tuple(change["ids"]) != tuple(need["ids"])]
        if (minimum, maximum) == (need["min"], need["max"]):
            print("    It is the row as the table has it." + (" Its change is removed." if was_changed else " Nothing to change."))
            continue
        changes.append({"ids": need["ids"], "min": minimum, "max": maximum, "on": True})
        print(f"    Changed: {need_change_text(need, minimum, maximum)}. It will be asked again for each new menu.")


def chosen_need_changes():
    """Returns the changes of the daily needs chosen at step 1.0, as {nutrient ids of the row: (min, max)}."""
    return {
        tuple(change["ids"]): (change["min"], change["max"])
        for change in load_menu_options().get("needs", []) if change["on"]
    }


def need_changes_cell(changes):
    """Writes changes of the daily needs (see chosen_need_changes) as a cell of successful_menus.csv: the ids of
    each row, its min and its max, empty without limit, as in "1003:120:150 1278+1272:0.25:"."""
    return " ".join(
        f"{'+'.join(map(str, ids))}:{minimum:g}:{'' if maximum is None else f'{maximum:g}'}"
        for ids, (minimum, maximum) in changes.items()
    )


def parse_need_changes(cell):
    """Returns the changes of the daily needs that a cell of successful_menus.csv tells (see need_changes_cell)."""
    changes = {}
    for change in cell.split():
        ids, minimum, maximum = change.split(":")
        changes[tuple(map(int, ids.split("+")))] = (float(minimum), float(maximum) if maximum else None)
    return changes


def need_changes_note(changes):
    """Says changes of the daily needs (see chosen_need_changes), one per line, nothing without any."""
    by_ids = {tuple(need["ids"]): need for need in load_daily_needs({})}
    return "\n".join(
        need_change_text(by_ids[ids], minimum, maximum) if ids in by_ids
        # A row that the table does not have anymore
        else f"nutrient {', '.join(map(str, ids))}: min {minimum:g}, max {'no limit' if maximum is None else f'{maximum:g}'}"
        for ids, (minimum, maximum) in changes.items()
    )


def menu_food_note():
    """Returns the lines of a prompt that tell the foods the menu must have and must not have, nothing without any."""
    options = load_menu_options()
    units = load_food_units()
    lines = []
    if options.get("include"):
        lines.append(MENU_INCLUDE_INTRO)
        lines += [
            f'- "{description}"' + (f" (a supplement: its amount is in {DOSE})" if units.get(fdc_id) == DOSE else "")
            for fdc_id, description in options["include"]
        ]
    if options.get("exclude"):
        lines.append(MENU_EXCLUDE_INTRO)
        lines += [f'- "{description}"' for _, description in options["exclude"]]
    return "".join(f"{line}\n" for line in lines)


def chosen_menu_options():
    """Returns the keys of the options chosen at step 1.0, and the other wishes."""
    options = load_menu_options()
    keys = [key for key, *_ in MENU_OPTIONS if options.get(key) and (key != "location" or options.get("address"))]
    return keys, options.get("other", "")


def menu_option_note(intro=MENU_OPTION_INTRO, chosen=None):
    """Returns the lines of a prompt that tell the wishes chosen at step 1.0, nothing when there is none.

    chosen gives the wishes of another menu instead, as (keys of its options, its other wishes).
    """
    keys, other = chosen or chosen_menu_options()
    address = load_menu_options().get("address", "")
    wishes = [text.format(address=address) for key, _, text, _ in MENU_OPTIONS if key in keys]
    if other:
        wishes.append(other)
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


def _read_successful_menus(rows, choices):
    """Returns the data rows of successful_menus.csv, and the numbers of its menus that are the menu (see load_menu)
    with the same products ({fdc_id: product_id})."""
    existing = []
    if SUCCESSFUL_MENU_FILE.exists():
        found, existing = read_csv(SUCCESSFUL_MENU_FILE)
        check_header(found, SUCCESSFUL_MENU_HEADER, SUCCESSFUL_MENU_FILE)
    menus = {}
    for row in existing:
        menus.setdefault(int(row[0]), set()).add((row[2], row[4], row[5], row[-1]))
    wanted = {(row[0], row[2], row[3], str(choices.get(int(row[0]), ""))) for row in rows}
    return existing, [number for number, foods in menus.items() if foods == wanted]


def save_successful_menu(rows, date, choices):
    """Adds the menu (see load_menu) to successful_menus.csv, the menus that satisfy the daily needs.

    Each of its rows starts with the number of the menu and its date, and ends with the options and the changes of
    the daily needs chosen at step 1.0, and the product the food was counted as (choices: {fdc_id: product_id}). Its text is saved too, in its own file.
    A menu that is already there with the same products is not added again.
    """
    existing, same = _read_successful_menus(rows, choices)
    if same:
        print(f"This menu is already the menu {same[0]} of '{SUCCESSFUL_MENU_FILE}'.")
        # The review of a menu may only change its text: when to eat what
        description = load_menu_description()
        if description and description != load_successful_menu_description(same[0]):
            SUCCESSFUL_MENU_DESCRIPTION_DIR.mkdir(exist_ok=True)
            (SUCCESSFUL_MENU_DESCRIPTION_DIR / f"{same[0]}.txt").write_text(description, encoding="utf-8")
            print("Its text is updated.")
        return
    number = max((int(row[0]) for row in existing), default=0) + 1
    keys, other = chosen_menu_options()
    changes = need_changes_cell(chosen_need_changes())
    write_csv(
        SUCCESSFUL_MENU_FILE,
        SUCCESSFUL_MENU_HEADER,
        existing + [[number, date, *row, " ".join(keys), other, changes, choices.get(int(row[0]), "")] for row in rows],
    )
    description = load_menu_description()
    if description:
        SUCCESSFUL_MENU_DESCRIPTION_DIR.mkdir(exist_ok=True)
        (SUCCESSFUL_MENU_DESCRIPTION_DIR / f"{number}.txt").write_text(description, encoding="utf-8")
    print(f"Saved as the menu {number} of '{SUCCESSFUL_MENU_FILE}'.")


def load_successful_menus():
    """Returns the menus of successful_menus.csv: {number: (date, keys of its options, other wishes, rows, products,
    changes)}.

    The rows are as in load_menu. products tells the product each food was counted as, as {fdc_id: product_id},
    changes the changes of the daily needs it was made with (see chosen_need_changes).
    """
    if not SUCCESSFUL_MENU_FILE.exists():
        return {}
    header, rows = read_csv(SUCCESSFUL_MENU_FILE)
    check_header(header, SUCCESSFUL_MENU_HEADER, SUCCESSFUL_MENU_FILE)
    menus = {}
    for number, date, *food, keys, other, changes, product_id in rows:
        menu = menus.setdefault(int(number), (date, keys.split(), other, [], {}, parse_need_changes(changes)))
        menu[3].append(food)
        if product_id:
            menu[4][int(food[0])] = int(product_id)
    return menus


def menu_block(rows, foods=None, choices=None):
    """Formats the menu (see load_menu) for a prompt.

    With foods ({fdc_id: description}), each row also has its ID and the real description of this ID. With choices
    ({fdc_id: product_id}) too, it also has the product it is counted as.
    """
    header = MENU_ANSWER_HEADER
    table = [row[1:] for row in rows]
    if foods is not None:
        header = header + ["fdc_id", "fdc_description"]
        table = [
            [*row[1:], row[0], foods[int(row[0])] if row[0].isdigit() else ""] for row in rows
        ]
    if choices is not None:
        products = load_products()
        header = header + ["product_id", "product"]
        for row in table:
            product_id = choices.get(int(row[3])) if row[3].isdigit() else None
            row += [product_id, products[product_id]["description"]] if product_id in products else ["", ""]
    return file_block(
        f"{MENU_FILE.name} (amount: for the whole day, in the unit of the row)", rows_to_csv(header, table)
    )


def menu_text(text):
    """Returns the menu as a text without what an LLM wrote before it: the code it ran, its outputs and its intro.

    The menu starts at its first title (a line in bold or a markdown title of level 2 or more: a '# ' line may be a
    comment of some code). A text without any title is kept whole.
    """
    lines = text.split("\n")
    start = next((index for index, line in enumerate(lines) if re.match(r"\*\*|#{2,6} ", line.strip())), 0)
    return "\n".join(lines[start:]).strip()


def split_menu_answer(text):
    """Returns (text of the menu, csv of the menu) of an LLM answer: the text is all that is written before the csv."""
    def is_header(line):
        try:
            cells = next(csv.reader([line]), [])
        except csv.Error:
            return False
        return set(MENU_ANSWER_HEADER) <= {cell.strip().lower() for cell in cells}

    lines = extract_csv(text).split("\n")
    starts = [index for index, line in enumerate(lines) if is_header(line)]
    if not starts:
        raise ValueError(f"No csv with the columns {MENU_ANSWER_HEADER} found in the clipboard.")
    # The csv may be in the same markdown block as the text, in its own one, or in none
    csv_text = "\n".join(lines[starts[-1]:])
    before = text[:text.rfind(csv_text)].split("\n")
    description = menu_text("\n".join(line for line in before if not line.strip().startswith("```")))
    if not description:
        raise ValueError(
            "The menu as a text is missing before the csv (the whole answer must be copied, not only its csv)."
        )
    return description, csv_text


def load_menu_description():
    """Returns the menu as a text, empty for a menu that was saved without it."""
    return menu_text(MENU_DESCRIPTION_FILE.read_text(encoding="utf-8")) if MENU_DESCRIPTION_FILE.exists() else ""


def save_menu_description(description):
    MENU_DESCRIPTION_FILE.write_text(description, encoding="utf-8")
    # The text is the one of the menu again
    MENU_TEXT_AMOUNT_FILE.unlink(missing_ok=True)


def load_menu_text_amounts(rows):
    """Returns the menu (see load_menu) with the amounts its text has, when step 6.0 computed the ones of rows since
    and the text was not written again. None when the text has the amounts of rows."""
    if not MENU_TEXT_AMOUNT_FILE.exists():
        return None
    header, written = read_csv(MENU_TEXT_AMOUNT_FILE)
    check_header(header, MENU_HEADER, MENU_TEXT_AMOUNT_FILE)
    # Only the amounts may differ
    same = [row[:2] + row[3:] for row in written] == [row[:2] + row[3:] for row in rows]
    return written if same else None


def save_menu_text_amounts(rows):
    """Keeps the menu (see load_menu) as its text describes it, before menu.csv gets amounts that step 6.0 computed."""
    if not MENU_TEXT_AMOUNT_FILE.exists():
        write_csv(MENU_TEXT_AMOUNT_FILE, MENU_HEADER, rows)


def menu_description_block(description):
    """Formats the menu as a text for a prompt."""
    return f"{MENU_DESCRIPTION_FILE.name} (the menu as a text, {MENU_FILE.name} was written from it)\n```\n{description}\n```"


def load_successful_menu_description(number):
    """Returns the text of a menu of successful_menus.csv, empty when it was saved without it."""
    path = SUCCESSFUL_MENU_DESCRIPTION_DIR / f"{number}.txt"
    return menu_text(path.read_text(encoding="utf-8")) if path.exists() else ""


def menu_tips_block():
    """Formats the goals and tips of the user for a prompt, nothing when the file is empty or missing."""
    tips = MENU_TIPS_FILE.read_text(encoding="utf-8").strip() if MENU_TIPS_FILE.exists() else ""
    return f"{MENU_TIPS_FILE.name} (my goals and tips)\n```\n{tips}\n```" if tips else ""


def review_prompt(description, rows, choices, notes="", changes=None):
    """Returns the prompt that asks for the risks and the problems of a menu (see load_menu) that satisfies the
    daily needs: what its totals do not show, as how its foods are eaten together.

    description is the menu as a text, empty without any, choices the product each food is counted as
    ({fdc_id: product_id}), notes the lines that tell the foods and the wishes it was made with, changes the changes
    of the daily needs it was made with (see chosen_need_changes), the ones chosen at step 1.0 when not given.
    """
    tips = menu_tips_block()
    blocks = [daily_need_block(changes)]
    if tips:
        blocks.append(tips)
    if description:
        blocks.append(menu_description_block(description))
    blocks.append(menu_block(rows, load_all_foods(), choices))
    judged = f"my goals and tips of {MENU_TIPS_FILE.name}, and with anything else you know" if tips else "what you know"
    blocks.append(
        f"""Above is my vegan menu for a day, as a text then as a table, fdc_description being the generic food of SR Legacy 2018 or of my own foods that each row is, and product the real product I buy for it, when I have one. Counted this way, the total of the day is between min and max for each nutrient of {DAILY_NEED_FILE.name}: this was computed, do not check it again.
Is there any risk or problem in the menu as the text describes it, that those totals do not show? Judge it with {judged}: what is eaten together or apart in each meal (a food that helps or blocks the absorption of a nutrient of another one), a food or an amount that is risky to have every day, a preparation that is missing or unsafe, ...
{notes}If there is none, only answer that there is none, without any text of the menu nor csv. If there are, tell them in a few sentences, then write the whole corrected menu, the total of the day staying between min and max for each nutrient.
{MENU_NOTE}
- In the csv, keep the description of the foods you keep unchanged, even when you change their amount."""
    )
    return "\n\n".join(blocks)


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


def check_menu_foods(rows):
    """Raises if the menu (see load_menu) lacks a food it must have, or has a food it must not have (step 1.0).

    A food it must have is written with the description of its ID: its row gets this ID.
    """
    options = load_menu_options()
    units = load_food_units()
    by_description = {normalize(row[1]): row for row in rows}
    errors = []
    for fdc_id, description in options.get("include", []):
        row = by_description.get(normalize(description))
        unit = units.get(fdc_id, GRAM)
        if row is None:
            errors.append(f'- the menu must have the food "{description}": its row of the csv must have exactly this description')
        elif row[3] != unit:
            errors.append(f'- the amount of "{description}" must be in {unit}, not in {row[3]}')
        else:
            row[0] = str(fdc_id)
    errors += [
        f'- the menu must not have the food "{description}", under any description'
        for _, description in options.get("exclude", []) if normalize(description) in by_description
    ]
    if errors:
        raise ValueError("The menu does not follow what I asked for its foods:\n" + "\n".join(errors))


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


def load_daily_needs(changes=None):
    """Returns the daily needs as a list of {ids, name, unit, min, max}.

    A need can cover several nutrients ("1278, 1272"): their amounts are summed.
    'ids' is empty for the rows without nutrient ID. 'max' is None when there is no limit.
    The min and the max of a row are those of its change (see chosen_need_changes) when it has one: changes gives
    them, the ones chosen at step 1.0 when not given.
    """
    nutrients = load_nutrients()
    if changes is None:
        changes = chosen_need_changes()

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
        if tuple(ids) in changes:
            needs[-1]["min"], needs[-1]["max"] = changes[tuple(ids)]
    return needs


def needed_nutrient_ids():
    """Returns the IDs of the nutrients of daily_need_table.csv, in its order."""
    return [nutrient_id for need in load_daily_needs() for nutrient_id in need["ids"]]


def daily_need_block(changes=None):
    """Formats the daily need table for a prompt, with the nutrient units and its changes (see load_daily_needs)."""
    rows = [
        [", ".join(map(str, need["ids"])), need["name"], need["unit"], f"{need['min']:g}",
         "" if need["max"] is None else f"{need['max']:g}"]
        for need in load_daily_needs(changes)
    ]
    return file_block(
        f"{DAILY_NEED_FILE.name} (min and max: for the whole day, an empty max meaning no limit)",
        rows_to_csv(["id", "name", "unit", "min", "max"], rows),
    )


# ---------------------------------------------------------
# Limits of the foods
# ---------------------------------------------------------
def load_food_limits():
    """Returns the least and the most of the foods that are accepted in a day, as {fdc_id: (min, max)}, None being
    no limit."""
    if not FOOD_LIMIT_FILE.exists():
        return {}
    header, rows = read_csv(FOOD_LIMIT_FILE)
    check_header(header, FOOD_LIMIT_HEADER, FOOD_LIMIT_FILE)
    limits = {}
    for line, row in enumerate(rows, start=2):
        if len(row) != len(header):
            raise ValueError(f"Malformed row {line} in {FOOD_LIMIT_FILE}: {row}")
        where = f"row {line} of {FOOD_LIMIT_FILE}"
        limits[to_int(row[0], f"fdc_id at {where}")] = (
            to_float(row[2], f"min at {where}") if row[2] else None,
            to_float(row[3], f"max at {where}") if row[3] else None,
        )
    return limits


def save_food_limits(limits):
    """Adds limits (see load_food_limits) to food_limit.csv, replacing the ones the same foods had."""
    foods = load_all_foods()
    limits = load_food_limits() | limits
    write_csv(FOOD_LIMIT_FILE, FOOD_LIMIT_HEADER, [
        [fdc_id, foods.get(fdc_id, ""), *("" if limit is None else f"{limit:g}" for limit in of_food)]
        for fdc_id, of_food in limits.items()
    ])


def limit_text(low, high, unit):
    """Says a limit of a food (see load_food_limits)."""
    parts = [f"{what} {limit:g} {unit}" for what, limit in (("at least", low), ("at most", high)) if limit is not None]
    return " and ".join(parts)


def within_limits(amount, limit):
    """Returns the amount of a food brought back within its limit (min, max), None being no limit."""
    low, high = limit
    if low is not None and amount < low:
        return low
    if high is not None and amount > high:
        return high
    return amount


def food_limit_block(fdc_ids=None):
    """Formats the limits of those foods for a prompt, all of them without any, nothing when there is none."""
    foods = load_all_foods()
    units = load_food_units()
    rows = [
        [fdc_id, foods.get(fdc_id, ""), units.get(fdc_id, GRAM), *("" if limit is None else f"{limit:g}" for limit in of_food)]
        for fdc_id, of_food in load_food_limits().items() if fdc_ids is None or fdc_id in fdc_ids
    ]
    if not rows:
        return ""
    return file_block(
        f"{FOOD_LIMIT_FILE.name} (the least and the most of those foods that I accept in a day, an empty one meaning no limit)",
        rows_to_csv(["fdc_id", "fdc_description", "unit", "min", "max"], rows),
    )


def parse_limit_answer(text, menu):
    """Strictly validates the limits of an LLM answer, which are for foods of the menu (see load_menu), and returns
    them (see load_food_limits)."""
    csv_text = extract_table(text, LIMIT_ANSWER_HEADER)
    if csv_text is None:
        raise ValueError(f"No csv with the columns {LIMIT_ANSWER_HEADER} found in the clipboard.")
    ids = {normalize(description): int(fdc_id) for fdc_id, description, _, _ in menu if fdc_id.isdigit()}
    limits = {}
    for line, record in parse_answer(csv_text, LIMIT_ANSWER_HEADER):
        if normalize(record["description"]) not in ids:
            raise ValueError(
                f"'{record['description']}' (row {line}) is not a food of the menu: write its description exactly as "
                "in the table of the menu."
            )
        low = to_float(record["min"], f"min at row {line}") if record["min"] else None
        high = to_float(record["max"], f"max at row {line}") if record["max"] else None
        if low is None and high is None:
            raise ValueError(f"'{record['description']}' (row {line}) has neither min nor max.")
        if (low is not None and low < 0) or (high is not None and high < (low or 0)):
            raise ValueError(f"Invalid limits at row {line}: the min cannot be negative, and the max cannot be under the min.")
        limits[ids[normalize(record["description"])]] = (low, high)
    return limits


# ---------------------------------------------------------
# Food pool
# ---------------------------------------------------------
def amount_step(amount, unit):
    """Returns what the amount of a food is a multiple of: a whole dose, or grams as precise as the amount is small."""
    if unit == DOSE:
        return 1
    return 5 if amount >= 100 else 1 if amount >= 10 else 0.5 if amount >= 2 else 0.1


def judged_needs(nutrient_db, daily_needs):
    """Returns the daily needs (see load_daily_needs) that can be judged for those foods ({fdc_id: {nutrient_id:
    amount}}): a nutrient that half of the foods have no data for cannot."""
    return [
        need for need in daily_needs
        if need["ids"]
        and 2 * sum(1 for nutrients in nutrient_db.values() if set(need["ids"]) - set(nutrients)) < len(nutrient_db)
    ]


def load_food_pool():
    """Returns the IDs of the foods of the pool, None when there is no pool yet."""
    if not FOOD_POOL_FILE.exists():
        return None
    header, rows = read_csv(FOOD_POOL_FILE)
    check_header(header, FOOD_POOL_HEADER, FOOD_POOL_FILE)
    # A manual food may have been removed since
    foods = load_all_foods()
    ids = [to_int(row[0], f"fdc_id in {FOOD_POOL_FILE}") for row in rows]
    return [fdc_id for fdc_id in dict.fromkeys(ids) if fdc_id in foods]


def add_to_food_pool(amounts):
    """Adds foods to the pool, with the most of each one in a day ({fdc_id: max}), and returns the ones it did not have.

    The max becomes the limit of a food that had none: the limit a food already has is kept.
    """
    foods = load_all_foods()
    pool = load_food_pool() or []
    added = [fdc_id for fdc_id in amounts if fdc_id not in pool]
    if added or not FOOD_POOL_FILE.exists():
        write_csv(FOOD_POOL_FILE, FOOD_POOL_HEADER, [[fdc_id, foods[fdc_id]] for fdc_id in pool + added])
    limits = load_food_limits()
    without = {
        fdc_id: (limits.get(fdc_id, (None, None))[0], most)
        for fdc_id, most in amounts.items() if limits.get(fdc_id, (None, None))[1] is None
    }
    if without:
        save_food_limits(without)
    return added


def start_food_pool():
    """Returns the IDs of the foods of the pool. The first time, it is made of the foods of the menus of
    successful_menus.csv, the most of each one being its largest amount in them."""
    pool = load_food_pool()
    if pool is None:
        most = {}
        for _, _, _, rows, _, _ in load_successful_menus().values():
            for fdc_id, _, amount, _ in rows:
                most[int(fdc_id)] = max(most.get(int(fdc_id), 0), float(amount))
        foods = load_all_foods()
        add_to_food_pool({fdc_id: amount for fdc_id, amount in most.items() if fdc_id in foods})
        pool = load_food_pool()
        print(
            f"The food pool is started with the {len(pool)} foods of the saved menus, in '{FOOD_POOL_FILE}'. The most of "
            f"each one in a day is its largest amount in them, in '{FOOD_LIMIT_FILE}': edit both files as you wish."
        )
    return pool


def food_pool_block(pool):
    """Formats the foods of the pool for a prompt, with the least and the most of each one in a day."""
    foods = load_all_foods()
    units = load_food_units()
    limits = load_food_limits()
    return file_block(
        f"{FOOD_POOL_FILE.name} (the foods I am willing to buy and eat, with the least and the most of each one in a day)",
        rows_to_csv(["fdc_id", "fdc_description", "unit", "min", "max"], [
            [fdc_id, foods[fdc_id], units.get(fdc_id, GRAM),
             *("" if limit is None else f"{limit:g}" for limit in limits.get(fdc_id, (None, None)))]
            for fdc_id in pool
        ]),
    )


def parse_pool_answer(text, foods):
    """Strictly validates the foods an LLM proposes for the pool, foods ({fdc_id: description}) being the real ones,
    and returns the most of each one in a day, as {fdc_id: max}."""
    claims, most = [], {}
    for line, record in parse_answer(text, POOL_ANSWER_HEADER):
        claims.append((line, record["fdc_id"], record["fdc_description"]))
        amount = to_float(record["max"], f"max at row {line}")
        if amount <= 0:
            raise ValueError(f"Invalid max {amount} at row {line}: it is the most of the food in a day.")
        if record["fdc_id"].isdigit():
            most[int(record["fdc_id"])] = amount
    check_food_ids(claims, foods)
    return most


# ---------------------------------------------------------
# Products
# ---------------------------------------------------------
def load_products():
    """Returns the products as {product_id: {fdc_id, description, shop, price, package_amount, eco, source, date}}.

    price and package_amount are None when they are not known.
    """
    if not PRODUCT_FILE.exists():
        return {}
    header, rows = read_csv(PRODUCT_FILE)
    check_header(header, PRODUCT_HEADER, PRODUCT_FILE)
    products = {}
    for line, row in enumerate(rows, start=2):
        if len(row) != len(header) or not row[2]:
            raise ValueError(f"Malformed row {line} in {PRODUCT_FILE}: {row}")
        where = f"row {line} of {PRODUCT_FILE}"
        products[to_int(row[0], f"product_id at {where}")] = {
            "fdc_id": to_int(row[1], f"fdc_id at {where}"),
            "description": row[2],
            "shop": row[3],
            "price": to_float(row[4], f"price at {where}") if row[4] else None,
            "package_amount": to_float(row[5], f"package_amount at {where}") if row[5] else None,
            "eco": row[6],
            "source": row[7],
            "date": row[8],
        }
    return products


def save_products(products):
    write_csv(PRODUCT_FILE, PRODUCT_HEADER, [
        [
            product_id, p["fdc_id"], p["description"], p["shop"],
            "" if p["price"] is None else f"{p['price']:g}",
            "" if p["package_amount"] is None else f"{p['package_amount']:g}",
            p["eco"], p["source"], p["date"],
        ]
        for product_id, p in products.items()
    ])


def load_product_nutrients():
    """Returns the nutrients given for the products as {product_id: {nutrient_id: (amount, source)}}."""
    if not PRODUCT_NUTRIENT_FILE.exists():
        return {}
    header, rows = read_csv(PRODUCT_NUTRIENT_FILE)
    check_header(header, PRODUCT_NUTRIENT_HEADER, PRODUCT_NUTRIENT_FILE)
    nutrients = {}
    for line, row in enumerate(rows, start=2):
        try:
            nutrients.setdefault(int(row[0]), {})[int(row[1])] = (float(row[2]), row[3])
        except (IndexError, ValueError) as e:
            raise ValueError(f"Malformed row {line} in {PRODUCT_NUTRIENT_FILE}: {row}") from e
    return nutrients


def save_product_nutrients(nutrients):
    write_csv(PRODUCT_NUTRIENT_FILE, PRODUCT_NUTRIENT_HEADER, [
        [product_id, nutrient_id, f"{amount:.6g}", source]
        for product_id, of_product in nutrients.items()
        for nutrient_id, (amount, source) in of_product.items()
    ])


def load_menu_products():
    """Returns the product each food is counted as, as {fdc_id: product_id}: the foods of the menu, and the ones
    of the menus before it."""
    if not MENU_PRODUCT_FILE.exists():
        return {}
    header, rows = read_csv(MENU_PRODUCT_FILE)
    check_header(header, MENU_PRODUCT_HEADER, MENU_PRODUCT_FILE)
    return {int(fdc_id): int(product_id) for fdc_id, product_id in rows}


def save_menu_products(choices):
    """Saves the product each food of the menu is counted as ({fdc_id: product_id}).

    The product of a food that the menu does not have anymore is kept: a later menu that has this food counts it
    as this product again.
    """
    saved = load_menu_products()
    choices = choices | {fdc_id: product_id for fdc_id, product_id in saved.items() if fdc_id not in choices}
    if choices != saved:
        write_csv(MENU_PRODUCT_FILE, MENU_PRODUCT_HEADER, list(choices.items()))


def choose_menu_products(fdc_ids):
    """Returns the product each of those foods of the menu is counted as, as {fdc_id: product_id}, and saves it.

    It is the product chosen before, or else the first product of the food. A food without any product is left out.
    """
    products = load_products()
    saved = load_menu_products()
    choices = {}
    for fdc_id in fdc_ids:
        of_food = [product_id for product_id, product in products.items() if product["fdc_id"] == fdc_id]
        if saved.get(fdc_id) in of_food:
            choices[fdc_id] = saved[fdc_id]
        elif of_food:
            choices[fdc_id] = of_food[0]
    save_menu_products(choices)
    return choices


def product_nutrient_db(nutrient_db, choices):
    """Returns the nutrients the foods are counted with ({fdc_id: {nutrient_id: amount}}), and where they come from.

    A food that is counted as a product (choices: {fdc_id: product_id}) has the nutrients given for the product, and
    the ones of the generic food for the others. The sources are {(fdc_id, nutrient_id): source}, only for the
    nutrients given for a product.
    """
    of_products = load_product_nutrients()
    db = {fdc_id: dict(nutrients) for fdc_id, nutrients in nutrient_db.items()}
    sources = {}
    for fdc_id, product_id in choices.items():
        for nutrient_id, (amount, source) in of_products.get(product_id, {}).items():
            db.setdefault(fdc_id, {})[nutrient_id] = amount
            sources[fdc_id, nutrient_id] = source
    return db, sources


def unchecked_foods(fdc_ids, choices):
    """Returns the foods that are not checked: those without a product, or whose product was not read on site."""
    products = load_products()
    of_products = load_product_nutrients()
    unchecked = []
    for fdc_id in fdc_ids:
        product_id = choices.get(fdc_id)
        sources = (
            [products[product_id]["source"], *(source for _, source in of_products.get(product_id, {}).values())]
            if product_id in products else [""]
        )
        if any(normalize(source) != ON_SITE for source in sources):
            unchecked.append(fdc_id)
    return unchecked


def menu_cost(menu, choices):
    """Returns the price of the menu (a list of (fdc_id, amount, unit)), and its foods that have no price."""
    products = load_products()
    cost = 0
    without_price = []
    for fdc_id, amount, _ in menu:
        product = products.get(choices.get(fdc_id), {})
        if product.get("price") is None or not product.get("package_amount"):
            without_price.append(fdc_id)
        else:
            cost += product["price"] * amount / product["package_amount"]
    return cost, without_price


def cost_note(menu, choices, descriptions):
    """Says what the menu (a list of (fdc_id, amount, unit)) costs, nothing while no food has a price."""
    cost, without_price = menu_cost(menu, choices)
    if len(without_price) == len(menu):
        return ""
    note = f"Price of the day: {cost:.2f} euros"
    if without_price:
        note += f", without the {len(without_price)} of its {len(menu)} foods that have no price"
        # A long list would hide the price
        if len(without_price) <= 5:
            note += ": " + ", ".join(descriptions[fdc_id] for fdc_id in without_price)
    return note + "."


def product_block(fdc_ids=None):
    """Formats the products of those foods for a prompt, all of them without any, with the generic food each one is."""
    foods = load_all_foods()
    rows = [
        [
            product_id, p["description"], p["fdc_id"], foods.get(p["fdc_id"], ""), p["shop"],
            "" if p["price"] is None else f"{p['price']:g}",
            "" if p["package_amount"] is None else f"{p['package_amount']:g}",
            p["eco"], p["source"],
        ]
        for product_id, p in load_products().items()
        if fdc_ids is None or p["fdc_id"] in fdc_ids
    ]
    return file_block(
        f"{PRODUCT_FILE.name} (the real products I buy; price: in euros for package_amount, in grams or in doses)",
        rows_to_csv(
            ["product_id", "product", "fdc_id", "fdc_description", "shop", "price", "package_amount", "eco", "source"],
            rows,
        ),
    )


def dependence_rows(menu, nutrient_db, needs):
    """Returns the rows of menu_dependence.csv: the nutrients of those needs that the menu (see load_menu) counts
    on each food for, the ones the food brings at least SHARE of the total of the day of."""
    # What each food brings: the nutrients are given for 100g of a food, or for one dose of a supplement
    brought = {
        int(fdc_id): {
            nutrient_id: nutrient_amount * (float(amount) if unit == DOSE else float(amount) / 100)
            for nutrient_id, nutrient_amount in nutrient_db[int(fdc_id)].items()
        }
        for fdc_id, _, amount, unit in menu
    }
    rows = []
    for fdc_id, description, _, _ in menu:
        fdc_id = int(fdc_id)
        for need in needs:
            # As in the report, a nutrient that half of the foods have no data for cannot be judged
            no_data = [i for i, nutrients in nutrient_db.items() if set(need["ids"]) - set(nutrients)]
            if not need["ids"] or 2 * len(no_data) >= len(nutrient_db):
                continue
            in_day = sum(brought[fdc_id].get(i, 0) for i in need["ids"])
            total = sum(of_food.get(i, 0) for of_food in brought.values() for i in need["ids"])
            if total > 0 and in_day >= SHARE * total:
                rows.append([
                    fdc_id, description, ", ".join(map(str, need["ids"])), need["name"], need["unit"],
                    f"{sum(nutrient_db[fdc_id].get(i, 0) for i in need['ids']):.4g}",
                    f"{in_day:.4g}", f"{total:.4g}", round(100 * in_day / total),
                    "yes" if total - in_day < need["min"] else "no",
                ])
    return rows


def dependence_block(menu, nutrient_db, needs):
    return file_block(
        "menu_dependence.csv (the nutrients the menu counts on each food for)",
        rows_to_csv(DEPENDENCE_HEADER, dependence_rows(menu, nutrient_db, needs)),
    )


def extract_table(text, required):
    """Returns the csv of an LLM answer that has those columns, None without any.

    The answer may hold several tables, each one in its own markdown block or ended by a blank line.
    """
    def is_header(line):
        try:
            cells = next(csv.reader([line]), [])
        except csv.Error:
            return False
        return set(required) <= {cell.strip().lower() for cell in cells}

    tables = []
    current = None
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip() or line.strip().startswith("```"):
            current = None
        elif current is not None:
            current.append(line)
        elif is_header(line):
            current = [line]
            tables.append(current)
    return "\n".join(tables[-1]) if tables else None


def answer_kind(text):
    """Tells what an LLM answer to the report holds: MENU_ANSWER, LIMIT_ANSWER or PRODUCT_ANSWER, None when it holds
    no csv of them."""
    if extract_table(text, MENU_ANSWER_HEADER) is not None:
        return MENU_ANSWER
    if extract_table(text, LIMIT_ANSWER_HEADER) is not None:
        return LIMIT_ANSWER
    if any(extract_table(text, header) is not None for header in (PRODUCT_ANSWER_HEADER, PRODUCT_NUTRIENT_ANSWER_HEADER)):
        return PRODUCT_ANSWER
    return None


def parse_product_answer(text, fdc_ids):
    """Strictly validates the products of an LLM answer, which replace foods among fdc_ids, and their nutrients.

    Returns the products as a list of dicts (see load_products, without date), and the nutrients as a list of
    (product, nutrient_id, amount, source), product being the ID of a product of product.csv, or the normalized
    description of a product of the answer.
    """
    product_csv = extract_table(text, PRODUCT_ANSWER_HEADER)
    nutrient_csv = extract_table(text, PRODUCT_NUTRIENT_ANSWER_HEADER)
    if product_csv is None and nutrient_csv is None:
        raise ValueError(
            f"No csv with the columns {PRODUCT_ANSWER_HEADER} nor {PRODUCT_NUTRIENT_ANSWER_HEADER} found in the clipboard."
        )
    # A table with its header alone is right when the other one has rows: no product whose label gives a nutrient,
    # or only nutrients of products that are already there
    product_csv, nutrient_csv = (table if table and "\n" in table.strip() else None for table in (product_csv, nutrient_csv))
    if product_csv is None and nutrient_csv is None:
        raise ValueError("The csv of the clipboard have no row: only their headers.")

    given = {}
    for line, record in parse_answer(product_csv, PRODUCT_ANSWER_HEADER) if product_csv else []:
        where = f"row {line} of the products"
        fdc_id = to_int(record["fdc_id"], f"fdc_id at {where}")
        if fdc_id not in fdc_ids:
            raise ValueError(f"Unexpected fdc_id {fdc_id} at {where}: it is not a food of the menu. Expected one of {sorted(fdc_ids)}.")
        if not record["product"]:
            raise ValueError(f"No product at {where}.")
        if normalize(record["product"]) in given:
            raise ValueError(f"The product '{record['product']}' is given twice ({where}).")
        price = to_float(record["price"], f"price at {where}") if record["price"] else None
        package_amount = to_float(record["package_amount"], f"package_amount at {where}") if record["package_amount"] else None
        if (price is not None and price < 0) or (package_amount is not None and package_amount <= 0):
            raise ValueError(f"Invalid price or package_amount at {where}.")
        if record["eco"].upper() not in (*ECO_LEVELS, ""):
            raise ValueError(f"Invalid eco '{record['eco']}' at {where}: it must be one of {', '.join(ECO_LEVELS)}, or empty.")
        if not record["source"]:
            raise ValueError(f"No source at {where}.")
        given[normalize(record["product"])] = {
            "fdc_id": fdc_id, "description": record["product"], "shop": record["shop"], "price": price,
            "package_amount": package_amount, "eco": record["eco"].upper(), "source": record["source"],
        }

    existing = load_products()
    by_description = {normalize(product["description"]): product_id for product_id, product in existing.items()}
    needed = set(needed_nutrient_ids())
    values = {}
    for line, record in parse_answer(nutrient_csv, PRODUCT_NUTRIENT_ANSWER_HEADER) if nutrient_csv else []:
        where = f"row {line} of the nutrients"
        name = normalize(record["product"])
        if name in given:
            product = name
        elif name.isdigit() and int(name) in existing:
            product = int(name)
        elif name in by_description:
            product = by_description[name]
        else:
            raise ValueError(
                f"Unknown product '{record['product']}' at {where}: it is neither a product of the first table, "
                f"nor the product_id or the description of a product of {PRODUCT_FILE.name}."
            )
        nutrient_id = to_int(record["nutrient_id"], f"nutrient_id at {where}")
        amount = to_float(record["amount"], f"amount at {where}")
        if nutrient_id not in needed:
            raise ValueError(f"Unexpected nutrient_id {nutrient_id} at {where}: it is not in daily_need_table.csv.")
        if amount < 0:
            raise ValueError(f"Negative amount at {where}.")
        if not record["source"]:
            raise ValueError(f"No source at {where}.")
        if (product, nutrient_id) in values:
            raise ValueError(f"Nutrient {nutrient_id} is given twice for '{record['product']}' ({where}).")
        values[product, nutrient_id] = (amount, record["source"])
    return list(given.values()), [(*key, *value) for key, value in values.items()]


def save_product_answer(given, values, date):
    """Saves the products and the nutrients of an answer (see parse_product_answer).

    A product that its food already has (same description) is updated, and so are the nutrients already given.
    Returns the products of the answer as {fdc_id: product_id}.
    """
    products = load_products()
    known = {(p["fdc_id"], normalize(p["description"])): product_id for product_id, p in products.items()}
    ids = {}
    for product in given:
        key = product["fdc_id"], normalize(product["description"])
        if key not in known:
            known[key] = max(products, default=0) + 1
        products[known[key]] = {**product, "date": date}
        ids[key[1]] = known[key]
    if given:
        save_products(products)
        print(f"Successfully wrote {len(given)} products to '{PRODUCT_FILE}'.")

    if values:
        nutrients = load_product_nutrients()
        for product, nutrient_id, amount, source in values:
            nutrients.setdefault(ids.get(product, product), {})[nutrient_id] = (amount, source)
        save_product_nutrients(nutrients)
        print(f"Successfully wrote {len(values)} nutrients of products to '{PRODUCT_NUTRIENT_FILE}'.")
    return {product["fdc_id"]: ids[normalize(product["description"])] for product in given}
