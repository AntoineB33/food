from common import (
    DOSE,
    MENU_NOTE,
    ask_menu_options,
    daily_need_block,
    food_manual_block,
    load_manual_foods,
    menu_food_note,
    menu_option_note,
    menu_tips_block,
    set_clipboard,
)

# Added when the user already has manual foods: one of them has no ingredients nor nutrients to look for at steps
# 3.0 to 4.0, a food written another way is a new one
FOOD_MANUAL_NOTE = f"""food_manual.csv lists the foods I already use that SR Legacy 2018 does not have: mostly supplements, their amount being in the unit of their row ({DOSE}: a number of doses). When the menu needs one of them, or a food that one of them can be, take this one and write its exact description in the csv, instead of a new food."""

# Added when the user wrote goals and tips: the review of step 6.0 judges the menu with them, so it is made with them
TIPS_NOTE = """menu_tips.txt holds my goals and tips: the menu must follow them, the daily nutrient needs coming first."""

PROMPT = """Give me a vegan menu for a day that satisfies all the daily nutrient needs of the table above: the total of the day must be between min and max for each of them."""

if __name__ == "__main__":
    # The foods and the wishes chosen here are also told by the prompts that correct the menu (steps 1.5 and 6.0)
    ask_menu_options()
    foods = f"{food_manual_block()}\n\n" if load_manual_foods() else ""
    food_note = f"{FOOD_MANUAL_NOTE}\n" if foods else ""
    tips = f"{menu_tips_block()}\n\n" if menu_tips_block() else ""
    tips_note = f"{TIPS_NOTE}\n" if tips else ""
    set_clipboard(
        f"{daily_need_block()}\n\n{tips}{foods}{PROMPT}\n{food_note}{tips_note}{menu_food_note()}{menu_option_note()}{MENU_NOTE}"
    )
    print("Paste it in a new discussion, copy the whole answer (the menu as a text, then its csv), then run 1.5_copy_menu_then_check.")
