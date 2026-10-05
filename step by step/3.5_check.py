from common import (
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_HEADER,
    NUTRIENT_ID_NOTE,
    daily_need_block,
    file_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_nutrient_csv,
    rows_to_csv,
    set_clipboard,
    unchecked_foods,
)

CHECK_PROMPT = f"Is the nutrient composition correct? If not, write the whole corrected csv.\n{NUTRIENT_ID_NOTE}\n"

if __name__ == "__main__":
    # 1. The foods whose nutrients were asked for at step 3.0
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: nothing to check.")

    # 2. The clipboard holds the nutrient csv answered to the prompt of step 3.0
    food_nutr = get_clipboard()
    try:
        rows = parse_food_nutrient_csv(food_nutr, {fdc_id for fdc_id, _ in foods})

        covered = {int(row[1]) for row in rows}
        missing = [description for fdc_id, description in foods if fdc_id not in covered]
        if missing:
            raise ValueError(f"The clipboard CSV gives no nutrient for: {', '.join(missing)}")
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}\n\n{NUTRIENT_ID_NOTE}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    set_clipboard(
        f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n"
        f"{file_block('Suggested nutrient composition', rows_to_csv(FOOD_NUTRIENT_HEADER, rows))}\n\n"
        f"{CHECK_PROMPT}"
    )
