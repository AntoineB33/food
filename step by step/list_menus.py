"""Lists the menus of successful_menus.csv that were made with the options the user asks for (see README.md)."""
from common import (
    MENU_OPTIONS,
    SUCCESSFUL_MENU_FILE,
    ask_yes_no,
    load_successful_menu_description,
    load_successful_menus,
)

MADE = {key: made for key, _, _, made in MENU_OPTIONS}

if __name__ == "__main__":
    menus = load_successful_menus()
    if not menus:
        raise SystemExit(f"'{SUCCESSFUL_MENU_FILE}' has no menu yet: step 5.0 adds the menus that satisfy the daily needs.")

    # 1. An option answered by n is not looked at: the menus made with it are listed too
    print(f"{len(menus)} menus are saved. Which ones to list?")
    wanted = {key for key in MADE if ask_yes_no(f"Only the menus made {MADE[key]}", False)}
    text = input("  Only the menus whose other wishes contain (Enter for any): ").strip().lower()

    # 2. The menus made with all the wanted options
    found = {
        number: menu
        for number, menu in menus.items()
        if wanted <= set(menu[1]) and text in menu[2].lower()
    }
    print(f"\n{len(found)} of the {len(menus)} menus were made with these options.")
    for number, (date, keys, other, rows) in found.items():
        # An option that MENU_OPTIONS does not have anymore is shown by its key
        made = ", ".join(MADE.get(key, key) for key in keys) or "without any option"
        print(f"\n{'=' * 20} Menu {number} ({date}) {'=' * 20}")
        print(f"Made {made}." + (f" Other wishes: {other}" if other else ""))
        # A menu saved before the text was asked has none
        text = load_successful_menu_description(number)
        if text:
            print(f"\n{text}\n\nTotal of the day:")
        for _, description, amount, unit in rows:
            print(f"{amount:>7} {unit:<5}{description}")
