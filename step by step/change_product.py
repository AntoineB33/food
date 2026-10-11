"""Makes another product the one a food is counted as, in the menus of successful_menus.csv too (see README.md)."""
import csv
import json
import re
from datetime import date

import pyperclip

from common import (
    DB_DIR,
    DOSE,
    ECO_LEVELS,
    ERROR_PROMPT,
    GRAM,
    MENU_FILE,
    ON_SITE,
    PRODUCT_FILE,
    PRODUCT_NUTRIENT_NOTE,
    SUCCESSFUL_MENU_FILE,
    ask_yes_no,
    build_report,
    choose_menu_products,
    daily_need_block,
    get_clipboard,
    load_all_foods,
    load_daily_needs,
    load_food_limits,
    load_food_nutrients,
    load_food_units,
    load_menu_review_state,
    load_nutrients,
    load_product_nutrients,
    load_products,
    load_successful_menus,
    menu_cost,
    menu_history_file,
    needed_nutrient_ids,
    normalize,
    parse_product_answer,
    product_block,
    product_key,
    product_nutrient_db,
    read_csv,
    restart_successful_menu,
    rows_to_csv,
    save_menu_products,
    save_product_nutrients,
    save_products,
    set_clipboard,
    set_successful_menu_products,
    within_limits,
)

# Where 0_run_all remembers the script that was run last (see its STATE_FILE)
RUN_STATE_FILE = DB_DIR / "run_state.json"

# The prompt that asks for the nutrients of the product from what its label says
NUTRIENT_PROMPT = f"""{PRODUCT_FILE.name} above has the product {{product_id}}, "{{description}}", which I buy for the food {{fdc_id}} ({{food}}). Below is what its label says. Without it, use your web search tool to read the page of this product: never invent what a label says.
Write the nutrients of this product, {PRODUCT_NUTRIENT_NOTE}
- product: {{product_id}} on every row.

The label of the product:
"""


def failing_lines(report):
    """Returns the lines of a report (see build_report) that tell its lacks and excesses."""
    return "\n".join(f"  {line}" for line in report.split("#### On Target")[0].split("\n") if line.startswith("- "))


def check_menus(generic_db, only=None, ask=False):
    """Counts each menu of successful_menus.csv as the products its foods are counted as from now on, and returns
    the numbers of the ones that do not satisfy their daily needs this way.

    A menu that still satisfies them is counted this way from now on, after a question with ask. One that does not
    keeps its products until it is corrected. With only, a set of foods, the other foods keep the product of the menu.
    """
    products = load_products()
    descriptions = load_all_foods()
    limits = load_food_limits()
    broken = []
    for number, (_, _, _, rows, own, changes) in load_successful_menus().items():
        fdc_ids = [int(row[0]) for row in rows]
        if any(fdc_id not in generic_db for fdc_id in fdc_ids):
            print(f"Menu {number} has a food without nutrients: it is not checked.")
            continue
        # A product may have been removed since
        own = {fdc_id: product_id for fdc_id, product_id in own.items() if product_id in products}
        wanted = choose_menu_products(fdc_ids)
        if only is not None:
            wanted = own | {fdc_id: product_id for fdc_id, product_id in wanted.items() if fdc_id in only}
        # The menu is judged as step 6.0 does, with the daily needs it was made with
        menu = [
            (int(fdc_id), within_limits(float(amount), limits.get(int(fdc_id), (None, None))), unit)
            for fdc_id, _, amount, unit in rows
        ]
        nutrient_db, _ = product_nutrient_db({fdc_id: generic_db[fdc_id] for fdc_id in fdc_ids}, wanted)
        report, failing = build_report(menu, nutrient_db, load_daily_needs(changes))
        changed = {fdc_id: wanted[fdc_id] for fdc_id in fdc_ids if fdc_id in wanted and own.get(fdc_id) != wanted[fdc_id]}
        names = "; ".join(
            f"'{descriptions[fdc_id]}' as the product {product_id} ({products[product_id]['description']}, "
            f"{products[product_id]['shop']})" for fdc_id, product_id in changed.items()
        )
        if failing:
            print(
                f"\nMenu {number} does not satisfy its daily needs " + (
                    f"with {names}. It keeps its products until it is corrected:" if changed
                    else "anymore, with the numbers its products have now:"
                )
            )
            print(failing_lines(report))
            broken.append(number)
        elif changed and (not ask or ask_yes_no(f"Menu {number} still satisfies its daily needs with {names}. Count it this way", True)):
            set_successful_menu_products(number, changed)
            before, after = menu_cost(menu, own)[0], menu_cost(menu, wanted)[0]
            print(
                f"Menu {number} still satisfies its daily needs: it is counted with {names} from now on. "
                f"Price of the day: {before:.2f} -> {after:.2f} euros."
            )
    return broken


def restart_menu(broken):
    """Makes the first of those menus of successful_menus.csv the menu that run.bat goes on with, unless another
    one is being made there."""
    if not broken:
        return
    numbers = ", ".join(map(str, broken))
    try:
        state = json.loads(RUN_STATE_FILE.read_text(encoding="utf-8"))
        # The state run.bat is left in when a menu is reviewed and saved
        busy = not (state["step"] == "6.0" and state["result"] == "ok" and state["prompt"] is None)
    except (OSError, ValueError, KeyError):
        state, busy = None, False
    print(f"\nTo correct: the menu{'s' if len(broken) > 1 else ''} {numbers} of '{SUCCESSFUL_MENU_FILE.name}'.")
    made = load_menu_review_state()[2]
    if busy and made in broken:
        print(f"The menu {made} is already the menu being made in run.bat: go on there, 6.0 judges it with its products of now.")
        return
    if busy and not ask_yes_no(
        f"A menu is being made in run.bat (step {state['step']}). Give it up to correct the menu {broken[0]} instead", False
    ):
        print("Nothing is changed in run.bat: finish the menu being made there, then start product.bat again and press Enter.")
        return
    number = broken[0]
    restart_successful_menu(number)
    history = menu_history_file(number)
    # As after step 5.5: Enter runs the report
    RUN_STATE_FILE.write_text(
        json.dumps({"step": "5.5", "result": "ok", "prompt": None, "history": history.name if history.exists() else None}),
        encoding="utf-8",
    )
    print(
        f"The menu {number} is the menu being made from now on: start run.bat and press Enter. It runs 6.0, which "
        "looks for other amounts of its foods, or else asks the LLM to correct it. Once reviewed, the corrected menu "
        f"takes the place of the menu {number}."
    )
    if len(broken) > 1:
        print("Then start product.bat again and press Enter, for the next menu to correct.")


def ask_old_product(products):
    """Asks the product to replace, and returns its ID, None when the user quits."""
    while True:
        answer = input(
            "\n>>> The product to replace, as its product_id or as the start of its row (17,4,Natura Force ...), "
            "Enter to quit: "
        ).strip()
        if not answer:
            return None
        match = re.fullmatch(r"(\d+)(?:\s*,\s*(\d+)(?:\s*,\s*(.+))?)?", answer)
        if not match:
            print("Write its product_id, alone or followed by its fdc_id and its description, as in the table above.")
            continue
        product_id = int(match[1])
        if product_id not in products:
            print(f"No product {product_id} in '{PRODUCT_FILE.name}'.")
            continue
        product = products[product_id]
        if match[2] and int(match[2]) != product["fdc_id"]:
            print(f"The product {product_id} is of the food {product['fdc_id']}, not {match[2]}: \"{product['description']}\".")
            continue
        if match[3]:
            # The description may be quoted and followed by the other columns of the row
            typed, wanted = match[3].strip(), normalize(product["description"])
            if normalize(next(csv.reader([typed]))[0]) != wanted and not normalize(typed.strip('"')).startswith(wanted):
                print(f"The product {product_id} is \"{product['description']}\", not \"{typed}\".")
                continue
            return product_id
        if ask_yes_no(f"Replace the product {product_id}, \"{product['description']}\" ({product['shop']})", True):
            return product_id


def ask_text(name, last, empty=True):
    while True:
        answer = input(f"  {name} [{last}]: ").strip()
        if answer == "-" and not empty:
            print(f"  A product must have a {name}.")
            continue
        return "" if answer == "-" else answer or last


def ask_number(name, last):
    while True:
        answer = input(f"  {name} [{'' if last is None else f'{last:g}'}]: ").strip().replace(",", ".")
        if not answer:
            return last
        if answer == "-":
            return None
        try:
            number = float(answer)
        except ValueError:
            number = -1
        if number > 0:
            return number
        print("  Write a number above 0, or - when it is not known.")


def ask_columns(product, unit):
    """Asks the columns of product.csv for the new product, the ones of the product it replaces being kept by Enter."""
    print(f"The new product (Enter keeps the value in brackets, - empties it). It is {ON_SITE}: you read it yourself.")
    new = dict(product)
    new["description"] = ask_text("description", product["description"], empty=False)
    new["shop"] = ask_text("shop", product["shop"])
    new["price"] = ask_number("price (euros, for the package)", product["price"])
    new["package_amount"] = ask_number(f"package_amount ({'doses' if unit == DOSE else 'grams'} in the package)", product["package_amount"])
    while True:
        new["eco"] = ask_text(f"eco ({ECO_LEVELS[0]}, the best, to {ECO_LEVELS[-1]})", product["eco"]).upper()
        if new["eco"] in (*ECO_LEVELS, ""):
            break
        print(f"  Write one of {', '.join(ECO_LEVELS)}, or - when it is not known.")
    return new | {"source": ON_SITE, "date": date.today().isoformat()}


def nutrient_table(of_product):
    names = load_nutrients()
    return rows_to_csv(
        ["nutrient_id", "name", "unit", "amount", "source"],
        [[nutrient_id, *names[nutrient_id], f"{amount:g}", source] for nutrient_id, (amount, source) in of_product.items()],
    )


def edit_nutrients(of_product, unit):
    """Asks the nutrients of the product that change, of_product ({nutrient_id: (amount, source)}) being the ones it
    has, and returns them all."""
    of_product = dict(of_product)
    names = load_nutrients()
    needed = needed_nutrient_ids()
    print(f"The nutrients given for the product, for {'one dose' if unit == DOSE else '100g'} of it, in the unit of the nutrient:")
    print(nutrient_table(of_product))
    print("A nutrient that is not given is the one of the generic food.")
    while True:
        answer = input(
            "    A nutrient, as its nutrient_id then its amount (1003,25), or then - to remove it "
            "(Enter when done, ? lists the nutrients): "
        ).strip()
        if not answer:
            return of_product
        if answer == "?":
            print("\n".join(f"      {nutrient_id} {names[nutrient_id][0]} ({names[nutrient_id][1]})" for nutrient_id in needed))
            continue
        match = re.fullmatch(r"(\d+)[\s,;:]+(-|\d+(?:[.,]\d+)?)", answer)
        if not match or int(match[1]) not in needed:
            print("    Write a nutrient_id of daily_need_table.csv, then its amount, as in: 1003,25")
            continue
        nutrient_id = int(match[1])
        if match[2] == "-":
            of_product.pop(nutrient_id, None)
            print(f"    {names[nutrient_id][0]}: the one of the generic food.")
        else:
            of_product[nutrient_id] = (float(match[2].replace(",", ".")), ON_SITE)
            print(f"    {names[nutrient_id][0]}: {of_product[nutrient_id][0]:g} {names[nutrient_id][1]}")


def ask_llm_nutrients(product_id, product, food):
    """Gives the prompt that asks the LLM for the nutrients of the product, and returns the ones of its answer
    ({nutrient_id: (amount, source)}), None when the user gives up."""
    prompt = NUTRIENT_PROMPT.format(product_id=product_id, description=product["description"], fdc_id=product["fdc_id"], food=food)
    prompt = f"{daily_need_block()}\n\n{product_block({product['fdc_id']})}\n\n{prompt}"
    set_clipboard(prompt)
    while True:
        answer = input(
            "\n>>> Paste it in a new discussion, with what the label says after it (its text or a photo), copy the csv "
            "of the nutrients, then press Enter (q gives up): "
        ).strip().lower()
        if answer == "q":
            return None
        if pyperclip.paste().split() == prompt.split():
            print("The clipboard still holds the prompt: copy the csv the LLM writes first.")
            continue
        try:
            given, values = parse_product_answer(get_clipboard(), {product["fdc_id"]})
            if given or any(product != product_id for product, _, _, _ in values):
                raise ValueError(f"Only the nutrients of the product {product_id} are asked: every row has {product_id} as product.")
        except ValueError as e:
            print(f"\nError in the csv of the clipboard:\n{e}")
            pyperclip.copy(f"{ERROR_PROMPT}\n{e}")
            print("The prompt that tells the LLM about it is in the clipboard: paste it in the same discussion.")
            continue
        return {nutrient_id: (amount, source) for _, nutrient_id, amount, source in values}


def main():
    products = load_products()
    if not products:
        raise SystemExit(f"'{PRODUCT_FILE}' has no product yet: step 5.5 saves the ones the LLM finds.")
    foods = load_all_foods()
    units = load_food_units()
    menus = load_successful_menus()
    generic_db = load_food_nutrients({int(row[0]) for _, _, _, rows, _, _ in menus.values() for row in rows})

    # 1. The menus that a change made before left to correct, or that do not count a food as its product yet
    broken = check_menus(generic_db, ask=True)

    # 2. The product to replace. counted: whether its food is counted as it from now on
    counted = choose_menu_products(list(dict.fromkeys(product["fdc_id"] for product in products.values())))
    print(f"\nThe products of '{PRODUCT_FILE.name}':")
    print(rows_to_csv(
        ["product_id", "fdc_id", "description", "shop", "price", "package_amount", "counted"],
        [
            [
                product_id, p["fdc_id"], p["description"], p["shop"], "" if p["price"] is None else f"{p['price']:g}",
                "" if p["package_amount"] is None else f"{p['package_amount']:g}",
                "yes" if counted.get(p["fdc_id"]) == product_id else "",
            ]
            for product_id, p in products.items()
        ],
    ))
    old_id = ask_old_product(products)
    if old_id is None:
        restart_menu(broken)
        return
    old = products[old_id]
    fdc_id = old["fdc_id"]
    unit = units.get(fdc_id, GRAM)
    nutrients = load_product_nutrients()

    # 3. The product that replaces it: another one that the food already has, or a new one, described from it
    new_id = None
    others = {product_id: p for product_id, p in products.items() if p["fdc_id"] == fdc_id and product_id != old_id}
    if others:
        print(f"'{foods[fdc_id]}' has those other products:")
        print("\n".join(f"  {product_id} {p['description']} ({p['shop']})" for product_id, p in others.items()))
        while True:
            answer = input("  The product_id of the one to count the food as, Enter to describe a new product: ").strip()
            if not answer or (answer.isdigit() and int(answer) in others):
                break
            print(f"  '{answer}' is not one of them.")
        new_id = int(answer) if answer else None
    if new_id is None:
        new = ask_columns(old, unit)
        # The same description in the same shop is the same product: its row is corrected
        same = [product_id for product_id, p in products.items() if product_key(p) == product_key(new)]
        new_id = same[0] if same else max(products) + 1
        if same:
            print(f"It is the product {new_id} itself (same description, same shop): its row is updated.")
        else:
            print(f"It is the new product {new_id}. The product {old_id} is kept in '{PRODUCT_FILE.name}'.")
        products[new_id] = new
        save_products(products)
        # The nutrients it starts with: its own, or else the ones of the product it replaces
        base = dict(nutrients.get(new_id if same else old_id, {}))
        while True:
            how = input(
                "  Its nutrients: k keeps the ones of the product it replaces, m modifies some by hand, l gives a "
                "prompt to ask an LLM for them [k]: "
            ).strip().lower() or "k"
            if how in ("k", "m", "l"):
                break
            print("  Answer k, m or l.")
        if how == "m":
            base = edit_nutrients(base, unit)
        elif how == "l":
            given = ask_llm_nutrients(new_id, new, foods[fdc_id])
            if given is None:
                print("The nutrients of the product it replaces are kept.")
            else:
                base = given
                print(nutrient_table(base))
        nutrients[new_id] = base
        save_product_nutrients(nutrients)

    # 4. The food is counted as it from now on, in the menu being made and in the next ones
    save_menu_products({fdc_id: new_id})
    print(f"\n'{foods[fdc_id]}' is counted as the product {new_id} ({products[new_id]['description']}, {products[new_id]['shop']}) from now on.")
    if MENU_FILE.exists() and str(fdc_id) in [row[0] for row in read_csv(MENU_FILE)[1]]:
        print(f"The menu being made ('{MENU_FILE.name}') has this food: run 6.0 again in run.bat to judge it with this product.")

    # 5. And in the saved menus that still satisfy their daily needs with it. The others are to correct
    # The menus that have this food are judged again: one of them that was to correct may not be anymore
    waiting = [number for number in broken if all(row[0] != str(fdc_id) for row in menus[number][3])]
    restart_menu(waiting + check_menus(generic_db, only={fdc_id}))


if __name__ == "__main__":
    main()
