import sys

from common import (
    NUTRIENT_ID_NOTE,
    NUTRIENT_UNIT_NOTE,
    daily_need_block,
    food_manual_block,
    load_identified_menu,
    load_manual_foods,
    manual_nutrient_food_ids,
    set_clipboard,
)

PROMPT = f"""For each food item of this list, give a value for all the needed nutrients. Write a text easy to copy in a csv format with those columns:
"id","fdc_id","nutrient_id","amount","data_points","derivation_id","min","max","median"
This is supposed to be an extension of food_nutrient.csv from SR Legacy 2018 from fdc.nal.usda.gov. Use the fdc_id of food_manual.csv.
{NUTRIENT_UNIT_NOTE}
{NUTRIENT_ID_NOTE}"""

if __name__ == "__main__":
    # The foods of the menu that are in no food database and have no nutrient yet
    in_menu = {fdc_id for fdc_id, _, _ in load_identified_menu()}
    with_nutrients = manual_nutrient_food_ids()
    foods = [food for food in load_manual_foods() if food[0] in in_menu and food[0] not in with_nutrients]
    if not foods:
        # Not an error, but exiting this way makes the .bat pause: the message must be read
        sys.exit("Every food of the menu already has its nutrients: nothing to ask Gemini. Go on with 4.0_get_report.")

    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n{PROMPT}")
