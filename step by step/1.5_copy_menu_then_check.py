from common import (
    MENU_ANSWER_HEADER,
    MENU_FILE,
    MENU_NOTE,
    MENU_OPTION_KEEP_INTRO,
    MENU_RULES,
    answer_note,
    daily_need_block,
    errors_to_llm,
    get_clipboard,
    load_menu,
    menu_block,
    menu_option_note,
    normalize,
    parse_menu_csv,
    save_menu,
    set_clipboard,
)

CHECK_PROMPT = f"""The table above is a vegan menu for a day. Is it correct? Every food must be vegan, the amounts must be realistic to eat in a day, and the total of the day must be between min and max for each nutrient of daily_need_table.csv.
{menu_option_note(MENU_OPTION_KEEP_INTRO)}{answer_note(MENU_ANSWER_HEADER)}
{MENU_RULES}"""

if __name__ == "__main__":
    # 1. The clipboard holds the menu csv answered to the prompt of step 1.0, 5.0 or of this step
    with errors_to_llm(MENU_NOTE):
        rows = parse_menu_csv(get_clipboard())

    # 2. A food that the menu already had keeps its ID: only the new ones are left to identify at step 2.0
    if MENU_FILE.exists():
        known = {(normalize(description), unit): fdc_id for fdc_id, description, _, unit in load_menu()}
        for row in rows:
            row[0] = known.get((normalize(row[1]), row[3]), "")

    # 3. Save the menu (the next steps read it from there), then ask whether it is right
    save_menu(rows)
    set_clipboard(f"{daily_need_block()}\n\n{menu_block(rows)}\n\n{CHECK_PROMPT}")
    print("Paste it in a new discussion. If the LLM writes a corrected csv, copy it and run this step again to save it.")
    print("If it says the menu is correct, go on with 2.0_get_food_prompt.")
