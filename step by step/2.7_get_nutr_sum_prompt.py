from common import (
    ERROR_PROMPT,
    FOOD_INGREDIENT_HEADER,
    FOOD_INGREDIENT_MANUAL_FILE,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_HEADER,
    NUTRIENT_ID_NOTE,
    check_header,
    daily_need_block,
    file_block,
    food_manual_block,
    get_clipboard,
    load_daily_needs,
    load_diet_nutrients,
    load_food_manual,
    load_sr_legacy_foods,
    parse_ingredient_csv,
    read_csv,
    rows_to_csv,
    save_to_nutrient_manual,
    set_clipboard,
    unchecked_foods,
    write_csv,
)

PROMPT = f"""The nutrient composition above was computed as the simple sum of the nutrients of the ingredients of each food item: for 100g of the food item, the amount of each ingredient times its SR Legacy value. A nutrient that SR Legacy does not give for an ingredient counts as 0.
Is it the real nutrient composition of those food items (cooking, fermentation, missing SR Legacy values, ...)? If not, write the whole corrected csv, with the same columns.
{NUTRIENT_ID_NOTE}"""


def save_to_ingredient_manual(ingredients):
    """Writes the ingredients to food_ingredient_manual.csv, replacing the rows of the same foods."""
    existing = []
    if FOOD_INGREDIENT_MANUAL_FILE.exists():
        header, existing = read_csv(FOOD_INGREDIENT_MANUAL_FILE)
        check_header(header, FOOD_INGREDIENT_HEADER, FOOD_INGREDIENT_MANUAL_FILE)

    kept = [row for row in existing if int(row[0]) not in ingredients]
    rows = [
        [fdc_id, ingredient_id, f"{quantity:g}"]
        for fdc_id, food_ingredients in ingredients.items() for ingredient_id, quantity in food_ingredients.items()
    ]
    write_csv(FOOD_INGREDIENT_MANUAL_FILE, FOOD_INGREDIENT_HEADER, kept + rows)
    print(f"Successfully wrote {len(rows)} ingredient records to '{FOOD_INGREDIENT_MANUAL_FILE}'.")


def sum_nutrients(ingredients):
    """Returns the food_nutrient rows of the foods, each needed nutrient being the sum of those of the ingredients.

    Also returns the nutrients that none of the ingredients of a food has, as {fdc_id: [nutrient_id]}.
    """
    needed = list(dict.fromkeys(nutrient_id for need in load_daily_needs() for nutrient_id in need["ids"]))
    db = load_diet_nutrients({i: 1.0 for food_ingredients in ingredients.values() for i in food_ingredients})

    rows, without_data = [], {}
    for fdc_id, food_ingredients in ingredients.items():
        for nutrient_id in needed:
            amounts = [
                quantity * db[ingredient_id][nutrient_id]
                for ingredient_id, quantity in food_ingredients.items() if nutrient_id in db[ingredient_id]
            ]
            if not amounts:
                without_data.setdefault(fdc_id, []).append(nutrient_id)
            # The ID is given by save_to_nutrient_manual
            rows.append(["", str(fdc_id), str(nutrient_id), f"{round(sum(amounts), 4):g}", "1", "1", "", "", ""])
    return rows, without_data


if __name__ == "__main__":
    # 1. The foods whose ingredients were asked for at step 2.6
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no ingredient expected.")
    sr_legacy = load_sr_legacy_foods()

    # 2. The clipboard holds the ingredient csv answered to the prompt of step 2.6
    try:
        ingredients = parse_ingredient_csv(get_clipboard(), {fdc_id for fdc_id, _ in foods}, set(sr_legacy))
    except ValueError as e:
        # Give the error back to Gemini
        set_clipboard(f"{ERROR_PROMPT}\n{e}")
        print("It tells Gemini about the error below: paste it to Gemini.")
        raise

    without_ingredient = [description for fdc_id, description in foods if fdc_id not in ingredients]
    if without_ingredient:
        print(f"No ingredient given, nutrients left to step 3.0: {', '.join(without_ingredient)}")

    # 3. Compute the nutrients before writing anything, then update both DB files
    rows, without_data = sum_nutrients(ingredients)
    save_to_ingredient_manual(ingredients)
    rows = save_to_nutrient_manual(rows)

    # 4. Ask whether the sum is the real composition
    ingredient_rows = [
        [fdc_id, ingredient_id, sr_legacy[ingredient_id], f"{quantity:g}"]
        for fdc_id, food_ingredients in ingredients.items() for ingredient_id, quantity in food_ingredients.items()
    ]
    ingredient_header = ["fdc_id", "ingredient_fdc_id", "ingredient_description", "quantity"]
    notes = "".join(
        f"\n- food {fdc_id}: nutrient_id {', '.join(map(str, nutrient_ids))}"
        for fdc_id, nutrient_ids in without_data.items()
    )
    set_clipboard(
        f"{daily_need_block()}\n\n"
        f"{food_manual_block([food for food in foods if food[0] in ingredients])}\n\n"
        f"{file_block(FOOD_INGREDIENT_MANUAL_FILE.name + ' (quantity: 1 means 100g, in 100g of the food item)', rows_to_csv(ingredient_header, ingredient_rows))}\n\n"
        f"{file_block('Rows updated in food_nutrient_manual.csv', rows_to_csv(FOOD_NUTRIENT_HEADER, rows))}\n\n"
        f"{PROMPT}"
        + (f"\n\nSR Legacy gives no value for any ingredient (amount set to 0) for:{notes}" if notes else "")
    )
