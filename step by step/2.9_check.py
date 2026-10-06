from common import (
    FOOD_INGREDIENT_MANUAL_FILE,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_MANUAL_FILE,
    NUTRIENT_ID_NOTE,
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

PROMPT = f"""The nutrient composition above was computed as the simple sum of the nutrients of the ingredients of each food item: for 100g of the food item, the amount of each ingredient times its SR Legacy value. A nutrient that SR Legacy does not give for an ingredient counts as 0.
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
            # A nutrient that SR Legacy does not give for an ingredient counts as 0
            amount = sum(
                quantity * db[ingredient_id].get(nutrient_id, 0.0) for ingredient_id, quantity in food_ingredients.items()
            )
            # The ID is given by save_to_nutrient_manual
            rows.append(["", str(fdc_id), str(nutrient_id), f"{round(amount, 4):g}", "1", "1", "", "", ""])
    return rows


if __name__ == "__main__":
    # 1. The foods whose ingredients were saved and checked at step 2.7
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no nutrient to compute.")

    new_ids = {fdc_id for fdc_id, _ in foods}
    ingredients = {}
    for fdc_id, ingredient_id, quantity in load_food_ingredients():
        if int(fdc_id) in new_ids:
            ingredients.setdefault(int(fdc_id), {})[int(ingredient_id)] = float(quantity)
    if not ingredients:
        raise ValueError(f"No ingredient in {FOOD_INGREDIENT_MANUAL_FILE.name} for the new foods: run step 2.7 first.")

    # 2. Write their nutrients as the sum of those of their ingredients
    rows = save_to_nutrient_manual(sum_nutrients(ingredients))

    # The foods still without any nutrient: no ingredient given
    with_nutrients = {int(row[1]) for row in read_csv(FOOD_NUTRIENT_MANUAL_FILE)[1]}
    without_nutrients = [food for food in foods if food[0] not in with_nutrients]

    # 3. Ask whether the sum is the real composition
    summed = [food for food in foods if food[0] in ingredients]
    prompt = f"{updated_nutrient_blocks(summed + without_nutrients, rows)}\n\n{PROMPT}"

    # No other step asks for the nutrients of the foods without ingredient
    if without_nutrients:
        prompt += (
            "\n\nNo ingredient was given for those food items: add their rows to the csv, "
            "with a value for all the needed nutrients:"
            + "".join(f"\n- food {fdc_id}: {description}" for fdc_id, description in without_nutrients)
        )
    set_clipboard(prompt)
