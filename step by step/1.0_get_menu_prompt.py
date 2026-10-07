from common import MENU_NOTE, daily_need_block, set_clipboard

PROMPT = f"""Give me a vegan menu for a day that satisfies all the daily nutrient needs of the table above: the total of the day must be between min and max for each of them.
{MENU_NOTE}"""

if __name__ == "__main__":
    set_clipboard(f"{daily_need_block()}\n\n{PROMPT}")
    print("Paste it in a new discussion, copy the csv of the menu, then run 1.5_copy_menu_then_check.")
