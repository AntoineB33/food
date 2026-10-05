from common import (
    FOOD_MANUAL_FILE,
    NUTRIENT_ID_NOTE,
    add_new_foods,
    confirm,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_list,
    set_clipboard,
    unchecked_foods,
)

PROMPT = f"""For each food item of this list, give a value for all the needed nutrients. Write a text easy to copy in a csv format with those columns:
"id","fdc_id","nutrient_id","amount","data_points","derivation_id","min","max","median"
This is supposed to be an extension of food_nutrient.csv from SR Legacy 2018 from fdc.nal.usda.gov. Use the corresponding IDs from SR Legacy and food_manual.csv
{NUTRIENT_ID_NOTE}"""


if __name__ == "__main__":
    # 1. Get the food list answered to the prompt of step 2.0 from the clipboard
    clipboard_content = get_clipboard()

    print("\n" + "=" * 40)
    print("CURRENT CLIPBOARD TEXT:")
    print("=" * 40)
    print(clipboard_content)
    print("=" * 40 + "\n")

    # 2. Append the new foods to food_manual.csv
    if confirm("Do you want to add the above food list to food_manual.csv?"):
        add_new_foods(parse_food_list(clipboard_content), load_food_manual())
    else:
        print("Skipping clipboard text processing...")

    # 3. Ask for the nutrients of the foods that are not checked yet
    foods = unchecked_foods(load_food_manual())
    if not foods:
        raise ValueError(f"Every food of {FOOD_MANUAL_FILE.name} is already checked: no nutrient to ask for.")

    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n{PROMPT}")
