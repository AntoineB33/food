from common import (
    FOOD_FILE,
    FOOD_MANUAL_FILE,
    FOOD_MANUAL_HEADER,
    NUTRIENT_ID_NOTE,
    append_csv_rows,
    confirm,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    read_csv,
    set_clipboard,
    unchecked_foods,
)

PROMPT = f"""For each food item of this list, give a value for all the needed nutrients. Write a text easy to copy in a csv format with those columns:
"id","fdc_id","nutrient_id","amount","data_points","derivation_id","min","max","median"
This is supposed to be an extension of food_nutrient.csv from SR Legacy 2018 from fdc.nal.usda.gov. Use the corresponding IDs from SR Legacy and food_manual.csv
{NUTRIENT_ID_NOTE}"""


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


def get_existing_ids(foods):
    """Returns the fdc_ids already used by SR Legacy and food_manual.csv."""
    header, rows = read_csv(FOOD_FILE)
    id_index = header.index("fdc_id")
    return {int(row[id_index]) for row in rows} | {fdc_id for fdc_id, _ in foods}


def add_new_foods(descriptions, foods):
    """Appends the foods that are not in food_manual.csv yet, with the smallest free IDs."""
    known = {description.lower() for _, description in foods}
    for description in descriptions:
        if description.lower() in known:
            print(f"Already in {FOOD_MANUAL_FILE.name}, skipped: {description}")
    descriptions = [d for d in descriptions if d.lower() not in known]

    existing_ids = get_existing_ids(foods)
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


if __name__ == "__main__":
    # 1. Get the food list answered to the prompt of step 2.0 from the clipboard
    clipboard_content = get_clipboard()

    print("\n" + "=" * 40)
    print("CURRENT CLIPBOARD TEXT:")
    print("=" * 40)
    print(clipboard_content)
    print("=" * 40 + "\n")

    # 2. Append the new foods to food_manual.csv
    if confirm("Do you want to add the above food list to food_manual.csv?"):
        add_new_foods(parse_food_list(clipboard_content), load_food_manual())
    else:
        print("Skipping clipboard text processing...")

    # 3. Ask for the nutrients of the foods that are not checked yet
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no nutrient to ask for.")

    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n{PROMPT}")
