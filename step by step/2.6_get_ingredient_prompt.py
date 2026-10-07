from common import (
    FOOD_MANUAL_FILE,
    add_new_foods,
    confirm,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_list,
    set_clipboard,
)

PROMPT = """For each food item of this list, give all its ingredients. Write a text easy to copy in a csv format with those columns:
"fdc_id","ingredient_fdc_id","ingredient_description","quantity"
fdc_id is the ID of the food item in food_manual.csv. ingredient_fdc_id is the ID of the ingredient in SR Legacy 2018 (fdc.nal.usda.gov): its fdc_id (between 167512 and 175304), not its NDB number. ingredient_description is the description of the ingredient with its state (e.g. "Kale, raw"): the IDs are verified against it. quantity is the amount of the ingredient in 100g of the food item, as a number where 1 means 100g.
Write one row per ingredient. Leave out the food items that have no ingredient in SR Legacy (e.g. a supplement)."""


if __name__ == "__main__":
    # 1. Get the food list answered to the prompt of step 2.0 from the clipboard
    clipboard_content = get_clipboard()

    print("\n" + "=" * 40)
    print("CURRENT CLIPBOARD TEXT:")
    print("=" * 40)
    print(clipboard_content)
    print("=" * 40 + "\n")

    # 2. The foods need an ID to be associated to their ingredients: append the new ones to food_manual.csv
    descriptions = parse_food_list(clipboard_content)
    if confirm("Do you want to add the above food list to food_manual.csv?"):
        add_new_foods(descriptions, load_food_manual())
    else:
        print("Skipping clipboard text processing...")

    # 3. Ask for the ingredients of the foods of the list
    listed = {description.lower() for description in descriptions}
    foods = [food for food in load_food_manual() if food[1].lower() in listed]
    missing = listed - {description.lower() for _, description in foods}
    if missing:
        raise ValueError(
            f"Those new foods have no ID yet, because they were not added to {FOOD_MANUAL_FILE.name} "
            f"(answer 'y' to add them): {', '.join(sorted(missing))}"
        )

    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(f"\n\n\n{food_manual_block(foods)}\n\n{PROMPT}")
