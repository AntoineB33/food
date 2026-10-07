from common import (
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_HEADER,
    NUTRIENT_ID_NOTE,
    NUTRIENT_UNIT_NOTE,
    daily_need_block,
    file_block,
    food_manual_block,
    get_clipboard,
    load_manual_foods,
    parse_food_nutrient_csv,
    rows_to_csv,
    save_to_nutrient_manual,
    set_clipboard,
)

CHECK_PROMPT = f"""Is this nutrient composition correct? {NUTRIENT_UNIT_NOTE}
If it is correct, only answer that it is correct, without any csv. If not, write the whole corrected csv, as a text easy to copy with the same columns.
{NUTRIENT_ID_NOTE}"""

if __name__ == "__main__":
    foods = load_manual_foods()
    if not foods:
        raise ValueError(f"{FOOD_MANUAL_FILE.name} has no food: no nutrient expected.")

    # 1. The clipboard holds the nutrient csv answered to the prompt of step 3.0 (or of this step)
    try:
        rows = parse_food_nutrient_csv(get_clipboard(), {fdc_id for fdc_id, _, _ in foods})
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}\n\n{NUTRIENT_ID_NOTE}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    # 2. Save it, then ask whether it is correct
    rows = save_to_nutrient_manual(rows)
    given = {int(row[1]) for row in rows}
    set_clipboard(
        f"{daily_need_block()}\n\n{food_manual_block([food for food in foods if food[0] in given])}\n\n"
        f"{file_block('Rows updated in food_nutrient_manual.csv', rows_to_csv(FOOD_NUTRIENT_HEADER, rows))}\n\n"
        f"{CHECK_PROMPT}"
    )
    print("If Gemini writes a corrected csv, copy it and run this step again to save it.")
