from common import MENU_NOTE, ask_menu_options, daily_need_block, menu_option_note, set_clipboard

PROMPT = """Give me a vegan menu for a day that satisfies all the daily nutrient needs of the table above: the total of the day must be between min and max for each of them."""

if __name__ == "__main__":
    # The wishes chosen here are also told by the prompts that correct the menu (steps 1.5 and 5.0)
    ask_menu_options()
    set_clipboard(f"{daily_need_block()}\n\n{PROMPT}\n{menu_option_note()}{MENU_NOTE}")
    print("Paste it in a new discussion, copy the csv of the menu, then run 1.5_copy_menu_then_check.")
