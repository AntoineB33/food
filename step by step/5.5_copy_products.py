from datetime import date

from common import (
    PRODUCT_NOTE,
    choose_menu_products,
    errors_to_llm,
    get_clipboard,
    load_menu,
    load_products,
    parse_product_answer,
    save_menu_products,
    save_product_answer,
)

if __name__ == "__main__":
    menu = load_menu()
    fdc_ids = [int(fdc_id) for fdc_id, _, _, _ in menu if fdc_id.isdigit()]

    # 1. The clipboard holds the answer to the prompt of step 5.0, or to a prompt of step 6.0 that corrects the
    # products: the csv of the products, the csv of their nutrients, or both
    with errors_to_llm(PRODUCT_NOTE):
        given, values = parse_product_answer(get_clipboard(), set(fdc_ids))
    chosen = save_product_answer(given, values, date.today().isoformat())

    # 2. A product that was just given is the one its food is counted as from now on
    choices = choose_menu_products(fdc_ids) | chosen
    save_menu_products(choices)
    products = load_products()
    for fdc_id, description, _, _ in menu:
        if fdc_id.isdigit() and int(fdc_id) in chosen:
            print(f"'{description}' is counted as the product {chosen[int(fdc_id)]} ({products[chosen[int(fdc_id)]]['description']}).")
    without_product = [description for fdc_id, description, _, _ in menu if fdc_id.isdigit() and int(fdc_id) not in choices]
    if without_product:
        print(f"{len(without_product)} foods of the menu still have no product, run 5.0_get_product_prompt again to ask for them: {', '.join(without_product)}.")
    print("Go on with 6.0_get_report.")
