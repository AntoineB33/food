import sys

from common import (
    FOOD_INGREDIENT_MANUAL_FILE,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_MANUAL_FILE,
    NUTRIENT_ID_NOTE,
    daily_need_block,
    food_manual_block,
    load_daily_needs,
    load_diet_nutrients,
    load_food_ingredients,
    load_food_manual,
    read_csv,
    save_to_nutrient_manual,
    set_clipboard,
    unchecked_foods,
    updated_nutrient_blocks,
)

# For the foods without ingredient: nothing to sum
BASE_PROMPT = f"""For each food item of this list, give a value for all the needed nutrients, for 100g of the food item. Write a text easy to copy in a csv format with those columns:
"id","fdc_id","nutrient_id","amount","data_points","derivation_id","min","max","median"
This is supposed to be an extension of food_nutrient.csv from SR Legacy 2018 from fdc.nal.usda.gov. Use the fdc_id of food_manual.csv.
{NUTRIENT_ID_NOTE}"""

PROMPT = f"""The nutrient composition above was computed as the simple sum of the nutrients of the ingredients of each food item: for 100g of the food item, the amount of each ingredient times its value in SR Legacy 2018 or food_nutrient_manual.csv. A nutrient that is not given for an ingredient counts as 0.
Check it and improve it if necessary: the real composition may not be a simple sum (cooking, fermentation, values missing in SR Legacy, ...).
Write the whole csv, corrected or not, as a text easy to copy with the same columns.
{NUTRIENT_ID_NOTE}"""


def sum_nutrients(ingredients):
    """Returns the food_nutrient rows of the foods, each needed nutrient being the sum of those of the ingredients."""
    needed = list(dict.fromkeys(nutrient_id for need in load_daily_needs() for nutrient_id in need["ids"]))
    db = load_diet_nutrients({i: 1.0 for food_ingredients in ingredients.values() for i in food_ingredients})

    rows = []
    for fdc_id, food_ingredients in ingredients.items():
        for nutrient_id in needed:
            # A nutrient that is not given for an ingredient counts as 0
            amount = sum(
                quantity * db[ingredient_id].get(nutrient_id, 0.0) for ingredient_id, quantity in food_ingredients.items()
            )
            # The ID is given by save_to_nutrient_manual
            rows.append(["", str(fdc_id), str(nutrient_id), f"{round(amount, 4):g}", "1", "1", "", "", ""])
    return rows


if __name__ == "__main__":
    # 1. The new foods, and the ingredients saved and checked at step 2.7
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no nutrient to compute.")

    new_ids = {fdc_id for fdc_id, _ in foods}
    ingredients = {}
    with_ingredients = set()
    without_id = False
    for fdc_id, ingredient_id, _, quantity in load_food_ingredients():
        if int(fdc_id) not in new_ids:
            continue
        with_ingredients.add(int(fdc_id))
        if ingredient_id:
            ingredients.setdefault(int(fdc_id), {})[int(ingredient_id)] = float(quantity)
        else:
            without_id = True

    # 2. The foods without ingredient (supplements, ingredients added at step 2.7) have nothing to sum, and
    # the others may be made of them: their nutrients are asked for first
    with_nutrients = set()
    if FOOD_NUTRIENT_MANUAL_FILE.exists():
        with_nutrients = {int(row[1]) for row in read_csv(FOOD_NUTRIENT_MANUAL_FILE)[1]}
    base = [food for food in foods if food[0] not in with_ingredients and food[0] not in with_nutrients]
    if base:
        set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(base)}\n\n{BASE_PROMPT}")
        # Not an error, but exiting this way makes the .bat pause: the message must be read
        sys.exit(
            f"NOTHING IS SUMMED YET. {len(base)} foods without ingredient have no nutrient "
            f"({', '.join(description for _, description in base)}): the prompt in the clipboard asks Gemini for them.\n"
            "1. Paste the prompt to Gemini and copy its csv answer.\n"
            "2. Run 3.0_check_nutr, which saves it (this step does not read the clipboard).\n"
            "3. Run 2.9_check_nutr again: it will then sum the nutrients of the other foods."
        )
    elif not ingredients:
        raise ValueError(f"No ingredient in {FOOD_INGREDIENT_MANUAL_FILE.name} for the new foods: run step 2.7 first.")
    else:
        # 3. Write the nutrients of the other foods as the sum of those of their ingredients
        rows = save_to_nutrient_manual(sum_nutrients(ingredients))

        # 4. Ask whether the sum is the real composition
        prompt = f"{updated_nutrient_blocks([food for food in foods if food[0] in ingredients], rows)}\n\n{PROMPT}"
        if without_id:
            prompt += (
                "\n\nThe ingredients without ingredient_fdc_id are in no food database: they are not counted in the sum. "
                "Add their nutrients to those of their food item."
            )
        set_clipboard(prompt)
