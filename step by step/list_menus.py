"""Lists the menus of successful_menus.csv that were made with the options the user asks for (see README.md)."""
import pyperclip

from common import (
    MENU_HEADER,
    MENU_OPTIONS,
    NUTRIENT_UNIT_NOTE,
    SUCCESSFUL_MENU_FILE,
    ask_yes_no,
    cost_note,
    file_block,
    load_food_nutrients,
    load_nutrients,
    load_products,
    load_successful_menu_description,
    load_successful_menus,
    needed_nutrient_ids,
    product_block,
    product_nutrient_db,
    rows_to_csv,
    unchecked_foods,
)

MADE = {key: made for key, _, _, made in MENU_OPTIONS}


def menu_tables(rows, choices):
    """Returns the csv of the foods of a menu (see load_menu), with the product each one is counted as
    ({fdc_id: product_id}), the csv of the nutrients they are counted with, then the csv of those products.

    Only the nutrients of daily_need_table.csv are given: SR Legacy has many others.
    """
    fdc_ids = [int(fdc_id) for fdc_id, _, _, _ in rows]
    names = load_nutrients()
    needed = needed_nutrient_ids()
    nutrients, sources = product_nutrient_db(load_food_nutrients(set(fdc_ids)), choices)
    nutrient_rows = [
        [fdc_id, nutrient_id, *names[nutrient_id], f"{nutrients[fdc_id][nutrient_id]:g}",
         sources.get((fdc_id, nutrient_id), "generic food")]
        for fdc_id in fdc_ids
        for nutrient_id in needed
        if nutrient_id in nutrients.get(fdc_id, {})
    ]
    tables = [
        file_block(
            "menu.csv (amount: for the whole day, in the unit of the row)",
            rows_to_csv([*MENU_HEADER, "product_id"], [[*row, choices.get(int(row[0]), "")] for row in rows]),
        ),
        file_block(
            "food_nutrient.csv (the nutrients the foods of the menu are counted with; source: where the number of a "
            "product comes from)",
            rows_to_csv(["fdc_id", "nutrient_id", "name", "unit", "amount", "source"], nutrient_rows),
        ),
        NUTRIENT_UNIT_NOTE,
    ]
    if choices:
        tables.append(product_block(set(choices)))
    return "\n\n".join(tables)


def menu_sheet(number, rows, choices):
    """Returns the menu (see load_menu) as a text to read: its text, then a markdown table of its foods, each one
    with all that is known of the product it is counted as ({fdc_id: product_id}), or else with the food alone."""
    products = load_products()
    header = [
        "food", "amount", "product", "shop", "price (euros)", "package", "price of the day (euros)", "eco", "source",
        "date",
    ]
    table = []
    for fdc_id, description, amount, unit in rows:
        # A food without product, or whose product was removed since, has only its own cells
        p = products.get(choices.get(int(fdc_id)))
        cells = [description, f"{amount} {unit}"]
        if p:
            priced = p["price"] is not None and p["package_amount"]
            cells += [
                p["description"], p["shop"],
                "" if p["price"] is None else f"{p['price']:g}",
                "" if p["package_amount"] is None else f"{p['package_amount']:g} {unit}",
                f"{p['price'] * float(amount) / p['package_amount']:.2f}" if priced else "",
                p["eco"], p["source"], p["date"],
            ]
        table.append(cells + [""] * (len(header) - len(cells)))
    lines = [header, ["---"] * len(header), *table]
    price = cost_note(
        [(int(fdc_id), float(amount), unit) for fdc_id, _, amount, unit in rows], choices,
        {int(fdc_id): description for fdc_id, description, _, _ in rows},
    )
    parts = [
        f"Menu {number}",
        load_successful_menu_description(number),
        "\n".join("| " + " | ".join(str(cell).replace("|", "/") for cell in line) + " |" for line in lines),
        price,
    ]
    return "\n\n".join(part for part in parts if part)


def checked_note(rows, choices):
    """Says whether a menu (see load_menu) is checked: every food is a product whose numbers were read on site."""
    unchecked = unchecked_foods([int(row[0]) for row in rows], choices)
    if not unchecked:
        return "Checked: every food is a product that was read on site."
    names = [description for fdc_id, description, _, _ in rows if int(fdc_id) in unchecked]
    return f"Not checked: {len(unchecked)} of the {len(rows)} foods are not a product read on site ({', '.join(names)})."


if __name__ == "__main__":
    menus = load_successful_menus()
    if not menus:
        raise SystemExit(f"'{SUCCESSFUL_MENU_FILE}' has no menu yet: step 6.0 adds the menus that satisfy the daily needs.")

    # 1. A menu is chosen by its number, or else by its options
    print(f"{len(menus)} menus are saved, numbered {', '.join(map(str, menus))}. Which ones to list?")
    while True:
        answer = input("  The number of a menu (Enter to choose by options instead): ").strip()
        if not answer or (answer.isdigit() and int(answer) in menus):
            break
        print(f"  '{answer}' is not the number of a saved menu.")

    if answer:
        found = {int(answer): menus[int(answer)]}
    else:
        # 2. The menus made with all the wanted options: an option answered by n is not looked at, the menus
        # made with it are listed too
        wanted = {key for key in MADE if ask_yes_no(f"Only the menus made {MADE[key]}", False)}
        only_checked = ask_yes_no("Only the menus whose foods are all products read on site", False)
        text = input("  Only the menus whose other wishes contain (Enter for any): ").strip().lower()
        found = {
            number: menu
            for number, menu in menus.items()
            if wanted <= set(menu[1]) and text in menu[2].lower()
            and not (only_checked and unchecked_foods([int(row[0]) for row in menu[3]], menu[4]))
        }
        print(f"\n{len(found)} of the {len(menus)} menus were made with these options.")
    products = load_products()
    for number, (date, keys, other, rows, choices) in found.items():
        # An option that MENU_OPTIONS does not have anymore is shown by its key
        made = ", ".join(MADE.get(key, key) for key in keys) or "without any option"
        print(f"\n{'=' * 20} Menu {number} ({date}) {'=' * 20}")
        print(f"Made {made}." + (f" Other wishes: {other}" if other else ""))
        print(checked_note(rows, choices))
        price = cost_note(
            [(int(fdc_id), float(amount), unit) for fdc_id, _, amount, unit in rows], choices,
            {int(fdc_id): description for fdc_id, description, _, _ in rows},
        )
        if price:
            print(price)
        # A menu saved before the text was asked has none
        text = load_successful_menu_description(number)
        if text:
            print(f"\n{text}\n\nTotal of the day:")
        for fdc_id, description, amount, unit in rows:
            # A product that was removed since is not shown
            product = products.get(choices.get(int(fdc_id)))
            print(f"{amount:>7} {unit:<5}{description}" + (f" -> {product['description']}, {product['shop']}" if product else ""))

    # 3. One of them, as a text to read, or as the tables to give to an LLM or to a spreadsheet
    while found:
        answer = input("\n>>> Number of a menu to copy to the clipboard (Enter to quit): ").strip()
        if not answer:
            break
        if not answer.isdigit() or int(answer) not in found:
            print(f"'{answer}' is not one of the menus listed above: {', '.join(map(str, found))}.")
            continue
        rows, choices = found[int(answer)][3:]
        if ask_yes_no("Its text and the table of its products, to read (n: its foods and their nutrients, as csv)", True):
            pyperclip.copy(menu_sheet(int(answer), rows, choices))
            print(f"The text of the menu {answer} and the table of its products have been copied to your clipboard.")
        else:
            pyperclip.copy(menu_tables(rows, choices))
            print(f"The foods of the menu {answer} and their nutrients have been copied to your clipboard.")
