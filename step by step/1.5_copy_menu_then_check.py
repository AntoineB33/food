from common import (
    MENU_FILE,
    MENU_NOTE,
    MENU_OPTION_KEEP_INTRO,
    check_menu_foods,
    daily_need_block,
    errors_to_llm,
    get_clipboard,
    load_menu,
    menu_block,
    menu_description_block,
    menu_food_note,
    menu_option_note,
    normalize,
    parse_menu_csv,
    save_menu,
    save_menu_description,
    set_clipboard,
    split_menu_answer,
)

CHECK_PROMPT = f"""Above is a vegan menu for a day, as a text then as a table. Is it correct? Every food must be vegan, the amounts must be realistic to eat in a day, and the total of the day must be between min and max for each nutrient of daily_need_table.csv.
Look for any inconsistency between the text and the table: a food of the text that the table does not have, a food of the table that the text does not have, an amount of the table that is not the sum of the amounts of the food in the text, a wrong conversion to grams.
{menu_food_note()}{menu_option_note(MENU_OPTION_KEEP_INTRO)}If it is correct, only answer that it is correct, without any text of the menu nor csv. If not, write the whole corrected menu.
{MENU_NOTE}"""

if __name__ == "__main__":
    # 1. The clipboard holds the answer to the prompt of step 1.0, 6.0 or of this step: the menu as a text, then its csv
    with errors_to_llm(MENU_NOTE):
        description, csv_text = split_menu_answer(get_clipboard())
        rows = parse_menu_csv(csv_text)
        # The foods the menu must have get their ID there
        check_menu_foods(rows)

    # 2. A food that the menu already had keeps its ID: only the new ones are left to identify at step 2.0
    if MENU_FILE.exists():
        known = {(normalize(description), unit): fdc_id for fdc_id, description, _, unit in load_menu()}
        for row in rows:
            row[0] = row[0] or known.get((normalize(row[1]), row[3]), "")

    # 3. Save the menu (the next steps read it from there), then ask whether it is right
    save_menu(rows)
    save_menu_description(description)
    set_clipboard(
        f"{daily_need_block()}\n\n{menu_description_block(description)}\n\n{menu_block(rows)}\n\n{CHECK_PROMPT}"
    )
    print("Paste it in a new discussion. If the LLM writes a corrected menu, copy its whole answer and run this step again to save it.")
    print("If it says the menu is correct, go on with 2.0_get_food_prompt.")
