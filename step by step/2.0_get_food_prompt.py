from common import (
    DOSE,
    FOOD_LIST_HEADER,
    NEW,
    SEARCH_NOTE,
    food_manual_block,
    load_all_foods,
    load_menu,
    menu_block,
    set_clipboard,
)

PROMPT = f"""Here are my menu for a day and food_manual.csv, my own foods, that SR Legacy 2018 from fdc.nal.usda.gov does not have. Find each food of the menu in SR Legacy 2018, or else in food_manual.csv.
{SEARCH_NOTE}
Write a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in FOOD_LIST_HEADER)}
- One row per row of the menu, with its description unchanged.
- fdc_id, fdc_description: the ID of the food in SR Legacy 2018 or in food_manual.csv, and its exact description there. They are checked against the databases, to see if they correspond.
- The databases do not have every cooking method, brand or variant: take the closest food, in the state the amount of the menu is weighed in (raw, cooked, dry, ...). A food of food_manual.csv whose unit is {DOSE} is only for a row of the menu in {DOSE}.
- Only when none of the two databases has the food or a close one (a dish, a supplement, a protein powder, ...): write {NEW} as fdc_id, with an empty fdc_description. Its ingredients will be asked later.
- The rows of the menu that already have an fdc_id were checked: keep it."""

if __name__ == "__main__":
    # The menu saved at step 1.5
    set_clipboard(f"{menu_block(load_menu(), load_all_foods())}\n\n{food_manual_block()}\n\n{PROMPT}")
    print("Paste it in a new discussion, copy the csv of the foods, then run 2.5_check_food.")
