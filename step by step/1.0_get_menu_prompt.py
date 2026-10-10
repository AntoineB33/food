from common import (
    MENU_NOTE,
    ask_menu_options,
    daily_need_block,
    load_products,
    menu_food_note,
    menu_option_note,
    product_block,
    set_clipboard,
)

# Added when the user already has products: a menu made of their foods has less to look for at step 5.0
PRODUCT_NOTE = """product.csv lists the real products I already buy, fdc_description being the generic food each one is. Prefer those foods when it does not make the menu worse."""

PROMPT = """Give me a vegan menu for a day that satisfies all the daily nutrient needs of the table above: the total of the day must be between min and max for each of them."""

if __name__ == "__main__":
    # The foods and the wishes chosen here are also told by the prompts that correct the menu (steps 1.5 and 6.0)
    ask_menu_options()
    products = f"{product_block()}\n\n" if load_products() else ""
    product_note = f"{PRODUCT_NOTE}\n" if products else ""
    set_clipboard(f"{daily_need_block()}\n\n{products}{PROMPT}\n{product_note}{menu_food_note()}{menu_option_note()}{MENU_NOTE}")
    print("Paste it in a new discussion, copy the whole answer (the menu as a text, then its csv), then run 1.5_copy_menu_then_check.")
