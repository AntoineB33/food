from common import (
    ERROR_PROMPT,
    FOOD_MANUAL_FILE,
    food_manual_block,
    get_clipboard,
    ingredient_block,
    load_food_manual,
    load_sr_legacy_foods,
    parse_ingredient_csv,
    save_to_ingredient_manual,
    set_clipboard,
    unchecked_foods,
)

CHECK_PROMPT = """The table above gives the ingredients of each food item of your menu, with the real SR Legacy 2018 description of each ingredient_fdc_id.
Is it correct? For each row, the description must be the ingredient you meant (same food, same state: raw, cooked, dry, ...). All the ingredients of each food item must be there, and their quantities must sum to 1 (100g of the food item).
If not, write the whole corrected csv, as a text easy to copy with those columns:
"fdc_id","ingredient_fdc_id","quantity\""""

if __name__ == "__main__":
    # 1. The foods whose ingredients were asked for at step 2.6
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no ingredient expected.")

    # 2. The clipboard holds the ingredient csv answered to the prompt of step 2.6 (or of this step)
    try:
        ingredients = parse_ingredient_csv(get_clipboard(), {fdc_id for fdc_id, _ in foods}, set(load_sr_legacy_foods()))
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    # 3. Save it (step 2.9 reads it from there), then ask whether the IDs are the right foods
    rows = save_to_ingredient_manual(ingredients)
    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(
        f"\n\n\n{food_manual_block([food for food in foods if food[0] in ingredients])}\n\n"
        f"{ingredient_block(rows)}\n\n{CHECK_PROMPT}"
    )
    print("If Gemini writes a corrected csv, copy it and run this step again to save it.")
