import json
from collections import defaultdict
from datetime import date

import common
from common import (
    DB_DIR,
    DEPENDENCE_NOTE,
    DOSE,
    MENU_NOTE,
    MENU_OPTION_KEEP_INTRO,
    ON_SITE,
    PRODUCT_NOTE,
    PRODUCT_NUTRIENT_NOTE,
    ask_yes_no,
    choose_menu_products,
    cost_note,
    daily_need_block,
    dependence_block,
    file_block,
    load_all_foods,
    load_daily_needs,
    load_food_nutrients,
    load_identified_menu,
    load_menu,
    load_menu_description,
    load_nutrients,
    load_product_nutrients,
    load_products,
    menu_block,
    menu_description_block,
    menu_option_note,
    normalize,
    product_block,
    product_nutrient_db,
    rows_to_csv,
    save_menu_products,
    save_successful_menu,
    set_clipboard,
)

# The corrections already asked for the menu, so that the next one is offered when a correction changed nothing
CORRECTION_FILE = DB_DIR / "correction_state.json"
# What a prompt of this step asks to correct, from the cheapest to the most expensive: wrong numbers of the
# products, products that suit the menu better, or the menu itself, which has to be identified again
VALUES, PRODUCTS, MENU = "values", "products", "menu"
CORRECTIONS = {
    VALUES: "the numbers of the products",
    PRODUCTS: "other products, that suit this menu better",
    MENU: "the menu itself",
}

INTRO = """Above is my vegan menu for a day, fdc_description being the generic food of SR Legacy 2018 or of my own foods that each row is, and product the real product I buy for it, when I have one. A food is counted with the nutrients given for its product, or else with those of its generic food. The report compares the total of the day with daily_need_table.csv."""

VALUES_PROMPT = f"""{INTRO}
product_values.csv lists the numbers behind these lacks and excesses that I did not read myself on the product: one of them may be wrong. Check each of them with your web search tool, on the page of the product.
If they are all right, only answer that they are right, without any csv. If not, write the rows to change, {PRODUCT_NUTRIENT_NOTE}"""

PRODUCTS_PROMPT = f"""{INTRO}
Without changing the foods of the menu nor their amounts, find other real products for some of them that would fix these lacks and excesses, without creating new ones: a product that is fortified or not, set with calcium or not, a supplement with another dose, ...
{DEPENDENCE_NOTE} It only has the nutrients in lack or in excess.
{menu_option_note("The menu was made with these wishes, follow them in the products you choose:")}Use your web search tool for the products, their prices and the shops. Never invent a product, a price or what a label says.
If no product can fix them, only answer so, without any csv. If some can, write them.
{PRODUCT_NOTE}"""

MENU_PROMPT = f"""{INTRO}
Correct the menu to fix these lacks and excesses, without creating new ones.
{menu_option_note(MENU_OPTION_KEEP_INTRO)}{MENU_NOTE}
- In the csv, keep the description of the foods you keep unchanged, even when you change their amount."""


def build_report(menu, nutrient_db, daily_needs):
    """Returns the report of the menu (a list of (fdc_id, amount, unit)), and its needs in lack or in excess."""
    # Sum the nutrients of the whole menu: they are given for 100g of a food, or for one dose of a supplement
    daily_totals = defaultdict(float)
    for fdc_id, amount, unit in menu:
        for nutrient_id, nutrient_amount in nutrient_db[fdc_id].items():
            daily_totals[nutrient_id] += nutrient_amount * (amount if unit == DOSE else amount / 100)

    lacks, excesses, on_target, unknown, failing = [], [], [], [], []
    for need in daily_needs:
        # The needs without nutrient ID cannot be computed from the databases
        if not need["ids"]:
            continue
        total = sum(daily_totals[nutrient_id] for nutrient_id in need["ids"])
        max_str = "no limit" if need["max"] is None else f"{need['max']:g}"
        record = f"- **{need['name']}** ({need['unit']}): {total:.2f} (Target: {need['min']:g} to {max_str})"

        # A food without data for a nutrient counts as 0: the total is then underestimated
        no_data = [str(fdc_id) for fdc_id, nutrients in nutrient_db.items() if set(need["ids"]) - set(nutrients)]
        if 2 * len(no_data) >= len(nutrient_db):
            # A total made of a few foods only tells nothing about the menu
            unknown.append(f"- **{need['name']}**: no data for {len(no_data)} of the {len(nutrient_db)} foods")
            continue
        if no_data:
            record += f" - data missing for the foods: {', '.join(no_data)}"

        if total < need["min"]:
            lacks.append(record)
            failing.append(need)
        elif need["max"] is not None and total > need["max"]:
            excesses.append(record)
            failing.append(need)
        else:
            on_target.append(record)

    report_lines = ["### Nutrition Gap Report", ""]
    for title, records in (
        ("Lacks (Under Minimum)", lacks),
        ("Excesses (Over Maximum)", excesses),
        ("On Target", on_target),
        ("Cannot be judged (the databases do not measure them: do not change the menu for them)", unknown),
    ):
        if records:
            report_lines += [f"#### {title}:", *records, ""]
    return "\n".join(report_lines).strip(), failing


def find_better_product(menu, generic_db, choices, daily_needs):
    """Returns the (fdc_id, product_id) of a product the user already has that makes the menu satisfy the daily
    needs when a food is counted as it instead, None without any."""
    for product_id, product in load_products().items():
        fdc_id = product["fdc_id"]
        if fdc_id in generic_db and choices.get(fdc_id) != product_id:
            nutrient_db, _ = product_nutrient_db(generic_db, choices | {fdc_id: product_id})
            if not build_report(menu, nutrient_db, daily_needs)[1]:
                return fdc_id, product_id
    return None


def unread_values(rows, choices, sources, failing):
    """Returns the rows of product_values.csv: the numbers of the products of the menu (see load_menu) that are
    behind the needs in lack or in excess, and that the user did not read on the product."""
    names = load_nutrients()
    products = load_products()
    of_products = load_product_nutrients()
    values = []
    for fdc_id in (int(row[0]) for row in rows):
        for nutrient_id in (nutrient_id for need in failing for nutrient_id in need["ids"]):
            # Only the nutrients given for a product have a source: the others are those of the generic food
            if normalize(sources.get((fdc_id, nutrient_id), ON_SITE)) != ON_SITE:
                product_id = choices[fdc_id]
                amount, source = of_products[product_id][nutrient_id]
                values.append([
                    product_id, products[product_id]["description"], nutrient_id, *names[nutrient_id], f"{amount:g}", source,
                ])
    return values


def ask_correction(rows, values):
    """Asks the user what to correct, offering the cheapest correction that was not asked for this menu yet."""
    # The corrections asked before only count while the menu is the same
    menu_key = json.dumps([[row[0], row[2], row[3]] for row in rows])
    try:
        state = json.loads(CORRECTION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    asked = state.get("asked", []) if state.get("menu") == menu_key else []

    possible = [kind for kind in CORRECTIONS if kind != VALUES or values]
    offered = next((kind for kind in possible if kind not in asked), MENU)
    print("\nWhat must the LLM correct?")
    for number, (kind, what) in enumerate(CORRECTIONS.items(), start=1):
        note = ""
        if kind == VALUES:
            note = (
                f": {len(values)} of the numbers behind the lacks and excesses were not read on site" if values
                else ": not possible, no number of a product is behind the lacks and excesses, or they were all read on site"
            )
        print(f"  {number}. {what}{note}{' (already asked for this menu)' if kind in asked else ''}")
    kinds = list(CORRECTIONS)
    while True:
        answer = input(f"  Your choice [{kinds.index(offered) + 1}]: ").strip()
        kind = offered if not answer else kinds[int(answer) - 1] if answer in ("1", "2", "3") else None
        if kind in possible:
            break
        print("  Answer one of the numbers that are possible.")
    CORRECTION_FILE.write_text(json.dumps({"menu": menu_key, "asked": [*asked, kind]}), encoding="utf-8")
    return kind


if __name__ == "__main__":
    # 1. The menu identified at step 2.5, whose new foods got their nutrients at steps 3.5 and 4.0. A food is
    # counted as the product chosen for it at step 5.5, or else as its generic food
    menu = load_identified_menu()
    rows = load_menu()
    fdc_ids = [fdc_id for fdc_id, _, _ in menu]
    generic_db = load_food_nutrients(set(fdc_ids))
    descriptions = load_all_foods()
    without_nutrient = [f"{fdc_id} ({descriptions[fdc_id]})" for fdc_id in fdc_ids if fdc_id not in generic_db]
    if without_nutrient:
        raise ValueError(f"No nutrient for the foods, run steps 3.0 to 4.0 first: {', '.join(without_nutrient)}.")
    choices = choose_menu_products(fdc_ids)
    nutrient_db, sources = product_nutrient_db(generic_db, choices)

    # 2. Compare the total of the day with the daily needs
    daily_needs = load_daily_needs()
    report, failing = build_report(menu, nutrient_db, daily_needs)
    print("\n" + "=" * 40)
    print(report)
    print("=" * 40)

    # 3. Another product that the user already has may be enough to satisfy them
    better = find_better_product(menu, generic_db, choices, daily_needs) if failing else None
    if better:
        products = load_products()
        instead = f"instead of '{products[choices[better[0]]]['description']}'" if better[0] in choices else "as its product"
        print(f"\nThe menu satisfies the daily needs when '{descriptions[better[0]]}' is counted as '{products[better[1]]['description']}' {instead}.")
        if ask_yes_no("Count it this way from now on", True):
            choices[better[0]] = better[1]
            save_menu_products(choices)
            nutrient_db, sources = product_nutrient_db(generic_db, choices)
            report, failing = build_report(menu, nutrient_db, daily_needs)

    price = cost_note(menu, choices, {int(row[0]): row[1] for row in rows})
    if price:
        print(price)
    if not failing:
        print("No nutrition lacks or excesses found. The menu satisfies the daily needs!")
        save_successful_menu(rows, date.today().isoformat(), choices)
    else:
        # 4. What to correct: the user chooses, the cheapest correction that was not asked yet being offered
        values = unread_values(rows, choices, sources, failing)
        common.last_correction = kind = ask_correction(rows, values)
        blocks = [daily_need_block(), menu_block(rows, descriptions, choices), report]
        if kind == VALUES:
            blocks.append(file_block(
                "product_values.csv (the numbers to check)",
                rows_to_csv(["product_id", "product", "nutrient_id", "name", "unit", "amount", "source"], values),
            ))
            blocks.append(VALUES_PROMPT)
            print("Paste it in a new discussion. If the LLM writes a csv, copy its whole answer, then run 5.5_copy_products and this step again.")
            print("If it says the numbers are right, run this step again to ask for another correction.")
        elif kind == PRODUCTS:
            blocks += [product_block(set(fdc_ids)), dependence_block(rows, nutrient_db, failing), PRODUCTS_PROMPT]
            print("Paste it in a new discussion. If the LLM writes csv tables, copy its whole answer, then run 5.5_copy_products and this step again.")
            print("If it says no product can fix them, run this step again to ask for another correction.")
        else:
            # A menu saved before the text was asked has none
            description = load_menu_description()
            if description:
                blocks.insert(1, menu_description_block(description))
            blocks.append(MENU_PROMPT)
            print("Paste it in a new discussion, copy the whole answer (the corrected menu as a text, then its csv), run 1.5_copy_menu_then_check to save it, then go on from 2.0_get_food_prompt.")
        set_clipboard("\n\n".join(blocks))
