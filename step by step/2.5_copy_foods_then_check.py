from common import (
    FOOD_LIST_HEADER,
    FOOD_MANUAL_FILE,
    GRAM,
    NEW,
    SEARCH_NOTE,
    answer_note,
    check_food_ids,
    errors_to_llm,
    food_manual_block,
    get_clipboard,
    load_all_foods,
    load_food_units,
    load_manual_foods,
    load_menu,
    menu_block,
    normalize,
    parse_answer,
    save_menu,
    save_new_foods,
    set_clipboard,
)

CHECK_PROMPT = f"""The first table above is my menu for a day, with the food each row was identified as: fdc_description is the real description of its fdc_id, in SR Legacy 2018 from fdc.nal.usda.gov or in food_manual.csv, my own foods. {NEW} as fdc_id means that none of the two databases has the food: its ingredients will be asked later.
Is it correct? For each row, fdc_description must be the food of description, or the closest food the databases have. They do not have every cooking method, brand or variant: a boiled or raw vegetable for a roasted or stir-fried one is right, and is not to be changed. The amount is the weight of the food in the state of fdc_description: dry oats or dry pasta weigh less than cooked ones. A food marked {NEW} must really be in none of the two databases, nor a close one.
{SEARCH_NOTE}
{answer_note(FOOD_LIST_HEADER)}
One row per row of the menu, with its description unchanged. fdc_description is the exact description of the fdc_id in its database, empty with {NEW}."""


def parse_food_list_csv(text, menu, foods):
    """Strictly validates the csv that identifies the foods of the menu, and returns the menu with its IDs."""
    units = load_food_units()
    manual = {normalize(description): fdc_id for fdc_id, description, _ in load_manual_foods()}
    menu_units = {normalize(description): unit for _, description, _, unit in menu}

    ids, claims = {}, []
    for line, record in parse_answer(text, FOOD_LIST_HEADER):
        key = normalize(record["description"])
        if key not in menu_units:
            raise ValueError(
                f"'{record['description']}' (row {line}) is not a food of the menu: keep its descriptions unchanged."
            )
        if key in ids:
            raise ValueError(f"'{record['description']}' is given twice (row {line}).")
        fdc_id = record["fdc_id"].lower()
        # A new food described exactly as a manual food is that food
        if fdc_id == NEW and key in manual:
            fdc_id = str(manual[key])
        elif fdc_id != NEW:
            claims.append((line, fdc_id, record["fdc_description"]))
        ids[key] = (line, fdc_id)

    missing = [description for _, description, _, _ in menu if normalize(description) not in ids]
    if missing:
        raise ValueError(f"Those foods of the menu have no row: {', '.join(missing)}")
    check_food_ids(claims, foods)
    for key, (line, fdc_id) in ids.items():
        if fdc_id != NEW and units.get(int(fdc_id), GRAM) != menu_units[key]:
            raise ValueError(
                f"Wrong food at row {line}: the amount of the food {fdc_id} ({foods[int(fdc_id)]}) is in "
                f"{units.get(int(fdc_id), GRAM)}, the one of the menu is in {menu_units[key]}."
            )
    return [[ids[normalize(description)][1], description, amount, unit] for _, description, amount, unit in menu]


if __name__ == "__main__":
    # 1. The clipboard holds the csv of the foods answered to the prompt of step 2.0 (or of this step)
    menu = load_menu()
    foods = load_all_foods()
    # The menu is given again with the error: the LLM may not have it anymore, or may have changed its descriptions
    with errors_to_llm(
        f"{menu_block(menu, foods)}\n\nWrite one row per row of menu.csv above, with its description exactly as it is "
        f"there. A food that is in none of the two databases has {NEW} as fdc_id.\n{SEARCH_NOTE}"
    ):
        menu = parse_food_list_csv(get_clipboard(), menu, foods)

    # 2. Save the IDs in the menu. The new foods of the menu before are forgotten: step 3.0 lists those of this one.
    save_menu(menu)
    save_new_foods([])
    new = [description for fdc_id, description, _, _ in menu if fdc_id == NEW]
    if new:
        print(f"In no database: {', '.join(new)}. Step 3.0 adds them to {FOOD_MANUAL_FILE.name}.")

    # 3. Ask whether it is right
    set_clipboard(f"{menu_block(menu, foods)}\n\n{food_manual_block()}\n\n{CHECK_PROMPT}")
    print("Paste it in a new discussion. If the LLM writes a corrected csv, copy it and run this step again to save it.")
    print("If it says it is correct, go on with 3.0_get_ingr_prompt.")
