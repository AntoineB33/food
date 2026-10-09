import sys

from common import (
    DEPENDENCE_NOTE,
    PRODUCT_NOTE,
    choose_menu_products,
    daily_need_block,
    dependence_block,
    load_all_foods,
    load_daily_needs,
    load_food_nutrients,
    load_menu,
    menu_block,
    menu_option_note,
    product_nutrient_db,
    set_clipboard,
)

PROMPT = f"""Above is my vegan menu for a day. Each food is counted with the nutrients of the generic food of SR Legacy 2018 or of food_manual.csv, my own foods, that fdc_description tells. The products I really buy may not have the same nutrients (fortified or not, set with calcium or not, what a dose of a supplement holds, ...).
{DEPENDENCE_NOTE}
Those foods of the menu have no real product yet:
{{foods}}
{menu_option_note("The menu was made with these wishes, follow them in the products you choose:")}Find for each of them a real product that I can buy. Use your web search tool for the products, their prices and the shops. Never invent a product, a price or what a label says: source tells where each information comes from.
{PRODUCT_NOTE}"""

if __name__ == "__main__":
    # 1. The menu identified at step 2.5, whose new foods got their nutrients at steps 3.5 and 4.0
    menu = load_menu()
    without_id = [description for fdc_id, description, _, _ in menu if not fdc_id.isdigit()]
    if without_id:
        raise ValueError(f"Those foods of the menu have no ID yet, finish steps 2.5 and 3.0 first: {', '.join(without_id)}")
    fdc_ids = [int(fdc_id) for fdc_id, _, _, _ in menu]
    generic_db = load_food_nutrients(set(fdc_ids))
    without_nutrient = [description for fdc_id, description, _, _ in menu if int(fdc_id) not in generic_db]
    if without_nutrient:
        raise ValueError(f"No nutrient for the foods, run steps 3.0 to 4.0 first: {', '.join(without_nutrient)}.")

    # 2. Only the foods that have no product yet are asked: the products are kept from a menu to the next
    choices = choose_menu_products(fdc_ids)
    asked = [f"- {fdc_id} ({description})" for fdc_id, description, _, _ in menu if int(fdc_id) not in choices]
    if not asked:
        # Not an error: exiting this way tells 0_run_all that the report is next
        sys.exit("Every food of the menu already has a product: nothing to ask the LLM. Go on with 6.0_get_report.")
    print(f"{len(asked)} of the {len(menu)} foods of the menu have no product yet: the prompt asks for them.")

    # 3. What the menu counts on each food for tells the LLM where the product to buy matters
    nutrient_db, _ = product_nutrient_db(generic_db, choices)
    set_clipboard(
        f"{daily_need_block()}\n\n{menu_block(menu, load_all_foods(), choices)}\n\n"
        f"{dependence_block(menu, nutrient_db, load_daily_needs())}\n\n{PROMPT.replace('{foods}', chr(10).join(asked))}"
    )
    print("Paste it in a new discussion, copy the whole answer (the csv of the products, then the csv of their nutrients), then run 5.5_copy_products.")
    print("The report does not need the products: 6.0_get_report counts a food without product as its generic food.")
