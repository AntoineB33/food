from common import (
    FOOD_LIMIT_FILE,
    LIMIT_NOTE,
    errors_to_llm,
    get_clipboard,
    limit_text,
    load_menu,
    parse_limit_answer,
    save_food_limits,
)

if __name__ == "__main__":
    menu = load_menu()

    # 1. The clipboard holds the answer to the prompt of step 6.0 that asks whether the computed amounts are realistic:
    # the csv of the limits of the foods whose amount is refused
    with errors_to_llm(f"Write the limits of the foods whose amount you refuse, {LIMIT_NOTE}"):
        limits = parse_limit_answer(get_clipboard(), menu)

    # 2. They are kept for every menu: the amounts that step 6.0 computes stay within them
    save_food_limits(limits)
    for fdc_id, description, _, unit in menu:
        if fdc_id.isdigit() and int(fdc_id) in limits:
            print(f"'{description}': {limit_text(*limits[int(fdc_id)], unit)} a day.")
    print(f"Saved in '{FOOD_LIMIT_FILE}', for this menu and the next ones: edit this file to change them.")
    print("Go on with 6.0_get_report: it computes the amounts again within them.")
