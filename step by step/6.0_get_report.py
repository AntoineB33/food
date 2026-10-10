import math
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from common import (
    DEPENDENCE_NOTE,
    DOSE,
    MENU_ANSWER_HEADER,
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
    menu_food_note,
    menu_option_note,
    menu_tips_block,
    normalize,
    product_block,
    product_nutrient_db,
    review_prompt,
    rows_to_csv,
    save_menu,
    save_menu_products,
    save_successful_menu,
    set_clipboard,
)

INTRO = """Above is my vegan menu for a day, fdc_description being the generic food of SR Legacy 2018 or of my own foods that each row is, and product the real product I buy for it, when I have one. A food is counted with the nutrients given for its product, or else with those of its generic food. The report compares the total of the day with daily_need_table.csv."""

# The corrections the LLM chooses from, from the cheapest for the user to the most expensive: wrong numbers of the
# products, products that suit the menu better, or the menu itself, which has to be identified again.
# The first one is only told when some numbers behind the lacks and excesses were not read on the product
VALUES_CORRECTION = f"""Check the numbers of product_values.csv with your web search tool, on the page of each product: they are the numbers behind these lacks and excesses that I did not read myself on the product, and one of them may be wrong. If some are wrong, write only the rows to change, {PRODUCT_NUTRIENT_NOTE}"""
PRODUCTS_CORRECTION = f"""Without changing the foods of the menu nor their amounts, find other real products for some of them that fix these lacks and excesses without creating new ones: a product that is fortified or not, set with calcium or not, a supplement with another dose, ... Use your web search tool for the products, their prices and the shops. Never invent a product, a price or what a label says. If some products do, write only them.
{menu_option_note("The menu was made with these wishes, follow them in the products you choose:")}{PRODUCT_NOTE}"""
# Told when the user wrote goals and tips: the review of a menu that satisfies the daily needs judges it with them
TIPS_NOTE = "Follow my goals and tips of menu_tips.txt in what you change.\n" if menu_tips_block() else ""
MENU_CORRECTION = f"""Correct the menu itself to fix these lacks and excesses, without creating new ones.
{TIPS_NOTE}{menu_food_note()}{menu_option_note(MENU_OPTION_KEEP_INTRO)}{MENU_NOTE}
- In the csv, keep the description of the foods you keep unchanged, even when you change their amount."""


# The amounts the script may give to a food to satisfy the daily needs: from its amount divided by this to its
# amount multiplied by it
RANGE = 2
# How far inside min and max the totals are aimed, as a share of them: a total that is just on one is counted out
MARGIN = 1e-6
# What a need out of its range by its whole min or max costs, a food whose amount doubles costing 1: when no amounts
# satisfy the needs, the closest ones to the needs are looked for before the closest ones to the menu
OUT_COST = 1000

AMOUNT_PROMPT = f"""Above is my vegan menu for a day, as a text then as a table. The amounts of the table were just computed so that the total of the day is between min and max for each of my daily nutrient needs: do not change them. The text still tells the amounts of before. These amounts changed:
{{changes}}
Write the menu again as a text with the amounts of the table, each one spread over the meals as the text spreads it now. If an amount is not realistic to eat in a day, say so in one sentence before the text, without changing it. Then write the table again as a csv, with the description, the amount and the unit of every food unchanged.
{MENU_NOTE}"""


def correction_prompt(with_values, still=None):
    """Returns the prompt that makes the LLM correct what is wrong, with the numbers to check when there are some.

    still are the names of the needs that no amounts of the foods of the menu satisfy, None when it was not looked for.
    """
    corrections = [PRODUCTS_CORRECTION, MENU_CORRECTION]
    if with_values:
        corrections.insert(0, VALUES_CORRECTION)
    amounts_note = "" if still is None else (
        "Changing only the amounts of the foods cannot fix them: menu_closest_amounts.csv has the amounts, between "
        f"the ones of the menu divided by {RANGE} and multiplied by {RANGE}, that come the closest to the daily needs, "
        f"and these needs are still out of their range with them: {', '.join(still)}. A product or a food must change "
        "for those ones, the other ones being fixed by amounts as these.\n"
    )
    return (
        f"{INTRO}\n{DEPENDENCE_NOTE} It only has the nutrients in lack or in excess.\n{amounts_note}"
        f"Fix these lacks and excesses with the first of the {len(corrections)} corrections below that can fix them. "
        "Go on to the next one only when the one before cannot: a correction of the menu costs me much more than a "
        "correction of the products. Start your answer by saying in one sentence which correction you make and why, "
        "then write what this correction asks for, and nothing of the other ones.\n\n"
        + "\n\n".join(f"Correction {number}. {text}" for number, text in enumerate(corrections, start=1))
    )


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


def amount_step(amount, unit):
    """Returns what the amount of a food is a multiple of: a whole dose, or grams as precise as the amount is small."""
    if unit == DOSE:
        return 1
    return 5 if amount >= 100 else 1 if amount >= 10 else 0.5 if amount >= 2 else 0.1


def solve_amounts(menu, nutrient_db, daily_needs, margin=MARGIN, strict=True):
    """Returns the amounts of the foods of the menu (a list of (fdc_id, amount, unit)) the closest to its own that
    satisfy the daily needs, None when no amounts do.

    A food keeps between its amount divided by RANGE and multiplied by it, a supplement at least one dose. The
    closest amounts are the ones whose changes, each one as a share of the amount, have the smallest sum: few foods
    change. Without strict, the needs that no amounts satisfy are left out of their range, by as little as possible.
    """
    # As in the report, a nutrient that half of the foods have no data for cannot be judged
    needs = [
        need for need in daily_needs
        if need["ids"] and (need["min"] > 0 or need["max"] is not None)
        and 2 * sum(1 for nutrients in nutrient_db.values() if set(need["ids"]) - set(nutrients)) < len(nutrient_db)
    ]
    foods, kept = len(menu), len(needs)
    steps = np.array([amount_step(amount, unit) for _, amount, unit in menu])
    amounts = np.array([amount for _, amount, _ in menu])

    # The unknowns: for each food, its amount as a number of steps, then how far it is from the amount of the menu,
    # as a share of it. Then for each need, how far the total is under its min and over its max, as a share of them
    size = 2 * foods + 2 * kept
    rows, lower, upper = [], [], []
    for index, need in enumerate(needs):
        # What one step of each food brings: the nutrients are given for 100g of a food, or for one dose
        brought = [
            sum(nutrient_db[fdc_id].get(nutrient_id, 0) for nutrient_id in need["ids"]) * (1 if unit == DOSE else 0.01)
            for fdc_id, _, unit in menu
        ]
        low, high = need["min"] * (1 + margin), None if need["max"] is None else need["max"] * (1 - margin)
        if high is not None and low > high:
            low, high = need["min"], need["max"]
        # Every need is counted as a share of its max, or else of its min: their units are very different
        scale = need["max"] or need["min"]
        row = np.zeros(size)
        row[:foods] = np.array(brought) * steps / scale
        row[2 * foods + index] = need["min"] / scale
        row[2 * foods + kept + index] = -(need["max"] or 0) / scale
        rows.append(row)
        lower.append(low / scale if need["min"] > 0 else -np.inf)
        upper.append(np.inf if high is None else high / scale)
    for index in range(foods):
        for sign in (1, -1):
            row = np.zeros(size)
            row[index], row[foods + index] = sign * steps[index] / amounts[index], -1
            rows.append(row)
            lower.append(-np.inf)
            upper.append(sign)

    cost = np.concatenate([np.zeros(foods), np.ones(foods), np.full(2 * kept, OUT_COST)])
    least = [max(1, amount / RANGE) if unit == DOSE else amount / RANGE for _, amount, unit in menu]
    bounds = Bounds(
        np.concatenate([np.ceil(np.array(least) / steps - 1e-9), np.zeros(foods + 2 * kept)]),
        np.concatenate([
            np.floor(amounts * RANGE / steps + 1e-9), np.full(foods, np.inf), np.full(2 * kept, 0 if strict else np.inf),
        ]),
    )
    result = milp(
        cost, constraints=LinearConstraint(np.array(rows), lower, upper), bounds=bounds,
        integrality=np.concatenate([np.ones(foods), np.zeros(foods + 2 * kept)]), options={"time_limit": 30},
    )
    if result.x is None:
        return None
    return [round(float(count) * float(step), 1) for count, step in zip(np.round(result.x[:foods]), steps)]


def closest_amounts(menu, nutrient_db, daily_needs):
    """Returns the amounts of the foods of the menu (a list of (fdc_id, amount, unit)) the closest to its own that
    satisfy the daily needs, and True. When no amounts do, the ones that come the closest to the needs, and False."""
    def satisfies(amounts):
        changed = [(fdc_id, amount, unit) for (fdc_id, _, unit), amount in zip(menu, amounts)]
        return not build_report(changed, nutrient_db, daily_needs)[1]

    # A total that no amount changes may be just on its min or its max: it is then aimed at them, not inside them
    for margin in (MARGIN, 0):
        amounts = solve_amounts(menu, nutrient_db, daily_needs, margin)
        if amounts and satisfies(amounts):
            return amounts, True
    amounts = solve_amounts(menu, nutrient_db, daily_needs, strict=False)
    return amounts, bool(amounts) and satisfies(amounts)


def amount_changes(rows, amounts):
    """Returns the lines that tell the foods of the menu (see load_menu) whose amount is not the one of amounts."""
    return [
        f"- {description}: {float(amount):g} {unit} -> {new:g} {unit}"
        for (_, description, amount, unit), new in zip(rows, amounts) if not math.isclose(float(amount), new)
    ]


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

    # 4. Other amounts of the same foods may be enough: there is then no food nor product to look for
    amounts, solved = closest_amounts(menu, nutrient_db, daily_needs) if failing else (None, False)
    changes = amount_changes(rows, amounts) if solved else []
    if changes:
        print(
            f"\nThe report above is the menu as it is: {len(failing)} of the daily needs are not satisfied. Changing only "
            f"the amounts of {len(changes)} of its {len(rows)} foods, as below, satisfies them all:"
        )
        print("\n".join(changes))

    if not failing:
        print("No nutrition lacks or excesses found. The menu satisfies the daily needs!")
        save_successful_menu(rows, date.today().isoformat(), choices)
        # The totals do not tell everything: the LLM looks for what is wrong in the way the menu is eaten
        notes = menu_food_note() + menu_option_note(MENU_OPTION_KEEP_INTRO)
        set_clipboard(review_prompt(load_menu_description(), rows, choices, notes), review=True)
        print("Paste it in a new discussion: it asks whether the menu has risks or problems that the totals do not show.")
        print("If the LLM writes a corrected menu, copy its whole answer and run 1.5_copy_menu_then_check. If it finds none, it is finished.")
    elif changes and ask_yes_no("Take these amounts (n: ask the LLM to correct the menu instead)", True):
        for row, amount in zip(rows, amounts):
            row[2] = f"{amount:g}"
        save_menu(rows)
        # The text of the menu still has the amounts of before: the LLM writes it again
        description = load_menu_description()
        blocks = [menu_description_block(description)] if description else []
        blocks += [menu_block(rows), AMOUNT_PROMPT.format(changes="\n".join(changes))]
        set_clipboard("\n\n".join(blocks))
        print("Paste it in a new discussion: it asks for the text of the menu with the new amounts.")
        print("Copy the whole answer and run 1.5_copy_menu_then_check to save it, then go on from 2.0_get_food_prompt: no food is new.")
    else:
        # 5. The LLM corrects what is wrong, among the numbers of the products, the products and the menu
        values = unread_values(rows, choices, sources, failing)
        blocks = [daily_need_block()]
        if menu_tips_block():
            blocks.append(menu_tips_block())
        # A menu saved before the text was asked has none
        description = load_menu_description()
        if description:
            blocks.append(menu_description_block(description))
        blocks += [menu_block(rows, descriptions, choices), report]
        if values:
            print(f"{len(values)} of the numbers behind the lacks and excesses were not read on site: the prompt asks to check them first.")
            blocks.append(file_block(
                "product_values.csv (the numbers to check)",
                rows_to_csv(["product_id", "product", "nutrient_id", "name", "unit", "amount", "source"], values),
            ))
        if choices:
            blocks.append(product_block(set(fdc_ids)))
        # When no amounts satisfy the needs, the closest ones tell which needs a product or a food must change for
        still = None
        if amounts and not solved:
            closest = amounts
            out = build_report([(fdc_id, new, unit) for (fdc_id, _, unit), new in zip(menu, closest)], nutrient_db, daily_needs)[1]
            still = [need["name"] for need in out]
            print(f"No amounts of the foods of the menu satisfy the daily needs. The closest ones leave out: {', '.join(still)}.")
            blocks.append(file_block(
                "menu_closest_amounts.csv (the amounts of the same foods that come the closest to the daily needs)",
                rows_to_csv(MENU_ANSWER_HEADER, [[row[1], f"{new:g}", row[3]] for row, new in zip(rows, closest)]),
            ))
        blocks += [dependence_block(rows, nutrient_db, failing), correction_prompt(bool(values), still)]
        set_clipboard("\n\n".join(blocks))
        print("Paste it in a new discussion, and copy the whole answer.")
        print("If the LLM corrected products, run 5.5_copy_products, then this step again.")
        print("If it corrected the menu, run 1.5_copy_menu_then_check to save it, then go on from 2.0_get_food_prompt.")
