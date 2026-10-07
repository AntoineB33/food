from common import (
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    NEW_INGREDIENT,
    add_new_foods,
    candidates_block,
    confirm,
    food_manual_block,
    get_clipboard,
    ingredient_check_block,
    load_all_foods,
    load_food_manual,
    parse_ingredient_csv,
    same_description,
    save_to_ingredient_manual,
    set_clipboard,
    unchecked_foods,
)

CHECK_PROMPT = """The table above gives the ingredients of each food item of your menu. ingredient_description is the ingredient you meant, real_description is the real description of its ingredient_fdc_id, in SR Legacy 2018 or in food_manual.csv (empty when the row has no ID).
Is it correct? For each row, real_description must be the ingredient you meant, or the closest food the databases have. They do not have every cooking method, brand or variant: a boiled or raw vegetable for a roasted or stir-fried one is right, and is not to be changed. All the ingredients of each food item must be there, and their quantities must sum to 1 (100g of the food item).
If it is correct, only answer that it is correct, without any csv. If not, write the whole corrected csv, as a text easy to copy with those columns:
"fdc_id","ingredient_fdc_id","ingredient_description","quantity"
ingredient_description is the ingredient you mean, in your own words if you do not know its real description.
Your memory of the IDs is not reliable: never write an ingredient_fdc_id that is not written in this message. Leave it empty instead: the foods will be searched from your ingredient_description. Leave the rows that are right as they are: never remove an ID because its food is only close to the ingredient."""

CANDIDATES_PROMPT = f"""For the rows without ingredient_fdc_id or whose two descriptions differ, those are the foods found from your ingredient_description, in SR Legacy 2018 and food_manual.csv. Take the ID of the right one, or else of the closest one (same food, another cooking method or variant), with its description as ingredient_description. Only if none of them is even close, describe the ingredient with other words (the foods will be searched again). If the ingredient is in none of the two databases (a supplement, a protein powder, ...), write {NEW_INGREDIENT} as its ingredient_fdc_id: it will be added to food_manual.csv."""

if __name__ == "__main__":
    # 1. The foods whose ingredients were asked for at step 2.6
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no ingredient expected.")

    # 2. The clipboard holds the ingredient csv answered to the prompt of step 2.6 (or of this step)
    known = load_all_foods()
    try:
        rows = parse_ingredient_csv(get_clipboard(), {fdc_id for fdc_id, _ in foods}, known)
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    # 3. The ingredients that are in no food database become manual foods, to have an ID.
    # Their nutrients are asked for at step 2.9.
    new = list(dict.fromkeys(description for _, ingredient_id, description, _ in rows if ingredient_id == NEW_INGREDIENT))
    if new:
        # Gemini may call new an ingredient that is already a manual food: it only takes its ID
        manual = {description.lower(): fdc_id for fdc_id, description in load_food_manual()}
        for description in new:
            if description.lower() in manual:
                print(f"Already in {FOOD_MANUAL_FILE.name}, its ID {manual[description.lower()]} is used: {description}")
        to_add = [description for description in new if description.lower() not in manual]
        if to_add:
            print("Ingredients that Gemini found in no food database:" + "".join(f"\n- {d}" for d in to_add))
            if not confirm(f"Do you want to add them to {FOOD_MANUAL_FILE.name}?"):
                raise ValueError("Those ingredients need an ID: nothing was saved.")
            add_new_foods(to_add, load_food_manual())
        ids = {description.lower(): str(fdc_id) for fdc_id, description in load_food_manual()}
        rows = [
            [fdc_id, ids[description.lower()] if ingredient_id == NEW_INGREDIENT else ingredient_id, description, quantity]
            for fdc_id, ingredient_id, description, quantity in rows
        ]
        own = [fdc_id for fdc_id, ingredient_id, _, _ in rows if fdc_id == ingredient_id]
        if own:
            raise ValueError(f"The foods {own} are given as their own ingredient.")
        known = load_all_foods()

    # 4. Save it (step 2.9 reads it from there), then ask whether the IDs are the right foods
    save_to_ingredient_manual(rows)
    given = {int(row[0]) for row in rows}
    prompt = (
        f"{food_manual_block([food for food in foods if food[0] in given])}\n\n"
        f"{ingredient_check_block(rows, known)}\n\n{CHECK_PROMPT}"
    )

    # Gemini cannot find the right ID by itself: search the foods it meant for it
    without_id = [description for _, ingredient_id, description, _ in rows if not ingredient_id]
    differing = [
        description for _, ingredient_id, description, _ in rows
        if ingredient_id and description and not same_description(description, known[int(ingredient_id)])
    ]
    if without_id or differing:
        # A food is not an ingredient of the foods it is asked for with
        searched = {fdc_id: description for fdc_id, description in known.items() if fdc_id not in given}
        prompt += f"\n\n{CANDIDATES_PROMPT}\n{candidates_block(without_id + differing, searched)}"
        print(f"{len(without_id)} ingredients have no ID, {len(differing)} are not described as their ID.")
    elif all(description for _, _, description, _ in rows):
        print(
            "Every ingredient has an ID and is described as it: the table is saved and ready for step 2.9. "
            "The prompt is only a last check of the ingredients and their quantities."
        )

    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(f"\n\n\n{prompt}")
    print("If Gemini writes a corrected csv, copy it and run this step again to save it.")
