from common import (
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_MANUAL_FILE,
    NUTRIENT_ID_NOTE,
    get_clipboard,
    load_food_ingredients,
    load_food_manual,
    parse_food_nutrient_csv,
    read_csv,
    save_to_nutrient_manual,
    set_clipboard,
    unchecked_foods,
    updated_nutrient_blocks,
)

CHECK_PROMPT = f"""Is this nutrient composition (for 100g of each food item) correct? If not, write the whole corrected csv, as a text easy to copy with the same columns.
{NUTRIENT_ID_NOTE}"""

if __name__ == "__main__":
    # 1. The foods whose nutrients were asked for at step 2.9
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: nothing to check.")

    # 2. The clipboard holds the nutrient csv answered to the prompt of step 2.9 (or of this step)
    try:
        rows = parse_food_nutrient_csv(get_clipboard(), {fdc_id for fdc_id, _ in foods})

        # Every new food without ingredient must have nutrients: the others get them from the sums of step 2.9
        covered = {int(row[1]) for row in rows}
        if FOOD_NUTRIENT_MANUAL_FILE.exists():
            covered |= {int(row[1]) for row in read_csv(FOOD_NUTRIENT_MANUAL_FILE)[1]}
        covered |= {int(row[0]) for row in load_food_ingredients()}
        missing = [f"{fdc_id} ({description})" for fdc_id, description in foods if fdc_id not in covered]
        if missing:
            raise ValueError(f"The csv gives no nutrient for the foods: {', '.join(missing)}")
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}\n\n{NUTRIENT_ID_NOTE}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    # 3. Save it, then ask whether it is correct
    rows = save_to_nutrient_manual(rows)
    given = {int(row[1]) for row in rows}
    set_clipboard(f"{updated_nutrient_blocks([food for food in foods if food[0] in given], rows)}\n\n{CHECK_PROMPT}")
    print("If Gemini writes a corrected csv, copy it and run this step again to save it.")
