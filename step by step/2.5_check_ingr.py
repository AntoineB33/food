from common import (
    DOSE,
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    GRAM,
    NEW_INGREDIENT,
    add_manual_foods,
    candidates_block,
    confirm,
    get_clipboard,
    load_all_foods,
    load_food_units,
    load_manual_foods,
    menu_check_block,
    parse_menu_csv,
    same_description,
    save_menu,
    set_clipboard,
)

CHECK_PROMPT = f"""The table above lists everything that is eaten or drunk in the day of your menu. ingredient_description is the ingredient you meant, real_description is the real description of its ingredient_fdc_id, in SR Legacy 2018 or in food_manual.csv (empty when the row has no ID).
Is it correct? For each row, real_description must be the ingredient you meant, or the closest food the databases have. They do not have every cooking method, brand or variant: a boiled or raw vegetable for a roasted or stir-fried one is right, and is not to be changed.
Every ingredient of the menu must be there, never a dish, with the amount eaten in the day: grams (unit {GRAM}), or number of doses for a supplement taken as a pill (unit {DOSE}). The amount is the weight of the food in the state of real_description: dry oats or dry pasta weigh less than cooked ones.
If it is correct, only answer that it is correct, without any csv. If not, write the whole corrected csv, as a text easy to copy with those columns:
"ingredient_fdc_id","ingredient_description","amount","unit"
ingredient_description is the ingredient you mean, in your own words if you do not know its real description.
Your memory of the IDs is not reliable: never write an ingredient_fdc_id that is not written in this message. Leave it empty instead: the foods will be searched from your ingredient_description. Leave the rows that are right as they are: never remove an ID because its food is only close to the ingredient."""

CANDIDATES_PROMPT = f"""For the rows without ingredient_fdc_id or whose two descriptions differ, those are the foods found from your ingredient_description, in SR Legacy 2018 and food_manual.csv. Take the ID of the right one, or else of the closest one (same food, another cooking method or variant), with its description as ingredient_description. Only if none of them is even close, describe the ingredient with other words (the foods will be searched again). If the ingredient is in none of the two databases (a supplement, a protein powder, ...), write {NEW_INGREDIENT} as its ingredient_fdc_id: it will be added to food_manual.csv."""

if __name__ == "__main__":
    # 1. The clipboard holds the menu csv answered to the prompt of step 2.0 (or of this step)
    foods = load_all_foods()
    try:
        rows = parse_menu_csv(get_clipboard(), foods, load_food_units())

        # A manual food cannot be added again with another unit
        manual = {description.lower(): (fdc_id, unit) for fdc_id, description, unit in load_manual_foods()}
        for fdc_id, description, _, unit in rows:
            known = manual.get(description.lower())
            if fdc_id == NEW_INGREDIENT and known and known[1] != unit:
                raise ValueError(
                    f"'{description}' is already the food {known[0]} of {FOOD_MANUAL_FILE.name}, whose amount is "
                    f"in {known[1]}: write its ID, with an amount in {known[1]}."
                )
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    # 2. An ingredient described exactly as a food is that food: no need to ask
    by_description = {}
    for fdc_id, description in foods.items():
        by_description.setdefault(" ".join(description.lower().split()), fdc_id)
    units = load_food_units()
    for row in rows:
        found = by_description.get(" ".join(row[1].lower().split()))
        if row[0] in ("", NEW_INGREDIENT) and found is not None and units.get(found, GRAM) == row[3]:
            row[0] = str(found)

    # 3. The ingredients that are in no food database become manual foods, to have an ID.
    # Their nutrients are asked for at step 3.0.
    new = list(dict.fromkeys((description, unit) for fdc_id, description, _, unit in rows if fdc_id == NEW_INGREDIENT))
    if new:
        print(
            "Ingredients that Gemini found in no food database:"
            + "".join(f"\n- {description} (in {unit})" for description, unit in new)
        )
        if not confirm(f"Do you want to add them to {FOOD_MANUAL_FILE.name}?"):
            raise ValueError("Those ingredients need an ID: nothing was saved.")
        add_manual_foods(new)
        ids = {description.lower(): str(fdc_id) for fdc_id, description, _ in load_manual_foods()}
        rows = [
            [ids[description.lower()] if fdc_id == NEW_INGREDIENT else fdc_id, description, amount, unit]
            for fdc_id, description, amount, unit in rows
        ]
        foods = load_all_foods()

    # 4. Save the menu (the next steps read it from there), then ask whether it is right
    save_menu(rows)
    prompt = f"{menu_check_block(rows, foods)}\n\n{CHECK_PROMPT}"

    # Gemini cannot find the right ID by itself: search the foods it meant for it
    without_id = [description for fdc_id, description, _, _ in rows if not fdc_id]
    differing = [
        description for fdc_id, description, _, _ in rows
        if fdc_id and description and not same_description(description, foods[int(fdc_id)])
    ]
    if without_id or differing:
        prompt += f"\n\n{CANDIDATES_PROMPT}\n{candidates_block(without_id + differing, foods)}"
        print(f"{len(without_id)} ingredients have no ID, {len(differing)} are not described as their ID.")
    else:
        print(
            "Every ingredient has an ID and is described as it: the menu is saved and ready for step 3.0. "
            "The prompt is only a last check of the ingredients and their amounts."
        )

    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(f"\n\n\n{prompt}")
    print("If Gemini writes a corrected csv, copy it and run this step again to save it.")
