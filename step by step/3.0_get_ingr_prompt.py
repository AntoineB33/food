import sys

from common import (
    DOSE,
    GRAM,
    INGREDIENT_HEADER,
    MENU_FILE,
    NEW,
    NONE,
    SEARCH_NOTE,
    food_manual_block,
    load_manual_foods,
    load_menu,
    load_new_foods,
    manual_nutrient_food_ids,
    new_food_block,
    normalize,
    register_manual_foods,
    save_menu,
    save_new_foods,
    set_clipboard,
)

PROMPT = f"""new_food.csv lists foods that SR Legacy 2018 from fdc.nal.usda.gov does not have: they were just added to food_manual.csv, my own foods. Give the ingredients of each food of new_food.csv, to deduce its nutrients from theirs.
{SEARCH_NOTE}
Write a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in INGREDIENT_HEADER)}
- One row per ingredient of a food. fdc_id is the food, from new_food.csv.
- ingredient_fdc_id, ingredient_description: the ID of the ingredient in SR Legacy 2018 or in food_manual.csv, and its exact description there. They are checked against the databases, to see if they correspond. The databases do not have every cooking method, brand or variant: take the closest food.
- quantity: the grams of the ingredient in 100g of the food when the unit of the food is {GRAM}, in one dose of it when its unit is {DOSE}. They do not have to sum to 100: a food loses or absorbs water when it is cooked. For an ingredient of food_manual.csv whose unit is {DOSE}: its number of doses instead of its grams.
- When none of the two databases has an ingredient or a close one: write {NEW} as ingredient_fdc_id, with your own ingredient_description. It will be added to new_food.csv, and its own ingredients will be asked.
- When the nutrients of a food cannot be deduced from ingredients (a supplement, an isolate, an extract, ...): give it a single row, with {NONE} as ingredient_fdc_id, and an empty ingredient_description and quantity. Its nutrients will be asked later."""

if __name__ == "__main__":
    # 1. The foods of the menu that step 2.5 found in no database become manual foods, to have an ID
    menu = load_menu()
    unidentified = [description for fdc_id, description, _, _ in menu if not fdc_id]
    if unidentified:
        raise ValueError(
            f"Those foods of {MENU_FILE.name} are not identified yet, finish step 2.5 first: {', '.join(unidentified)}"
        )
    added = set()
    if any(fdc_id == NEW for fdc_id, _, _, _ in menu):
        ids = register_manual_foods([(description, unit) for fdc_id, description, _, unit in menu if fdc_id == NEW])
        for row in menu:
            if row[0] == NEW:
                row[0] = str(ids[normalize(row[1])])
                added.add(int(row[0]))
        save_menu(menu)

    # 2. The new foods: those ones, and every manual food that still has no nutrient
    with_nutrients = manual_nutrient_food_ids()
    listed = added | {fdc_id for fdc_id, _, _ in load_new_foods()}
    new_foods = [food for food in load_manual_foods() if food[0] in listed or food[0] not in with_nutrients]
    save_new_foods(new_foods)
    if not new_foods:
        # Not an error: exiting this way tells 0_run_all that the products are next
        sys.exit("Every food of the menu already has its nutrients: nothing to ask the LLM. Go on with 5.0_get_product_prompt.")

    set_clipboard(f"{food_manual_block()}\n\n{new_food_block(new_foods)}\n\n{PROMPT}")
    print("Paste it in a new discussion, copy the csv of the ingredients, then run 3.5_copy_ingr_then_check.")
