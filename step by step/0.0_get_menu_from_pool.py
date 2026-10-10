import statistics
import sys

from common import (
    FOOD_LIMIT_FILE,
    FOOD_POOL_FILE,
    GRAM,
    MENU_FILE,
    POOL_NOTE,
    ask_menu_options,
    ask_yes_no,
    choose_menu_products,
    daily_need_block,
    food_manual_block,
    food_pool_block,
    judged_needs,
    load_all_foods,
    load_daily_needs,
    load_food_limits,
    load_food_nutrients,
    load_food_units,
    load_menu_options,
    load_products,
    load_successful_menus,
    menu_option_note,
    menu_tips_block,
    product_nutrient_db,
    save_menu,
    save_menu_description,
    set_clipboard,
    start_food_pool,
)
from solver import DIFFERENT, FOOD_COST, day_totals, solve_menu

# The prompt that asks for other foods for the pool: the needs that no menu of the pool satisfies are told when
# there are some
POOL_PROMPT = f"""food_pool.csv lists the foods I am willing to buy and eat. A vegan menu for a day is computed from them: the cheapest one whose total of the day is between min and max for each nutrient of daily_need_table.csv, each food having at most its max.
{{reason}}
{{wishes}}{{tips}}{POOL_NOTE}"""
UNMET_REASON = """No menu of those foods satisfies the daily needs. With the closest one, these needs are still out of their range:
{unmet}
Propose 5 to 15 other foods that bring what lacks without bringing what is in excess, the ones that bring the most of it for their price first."""
MORE_REASON = """Propose 10 to 20 other foods that would make the menus cheaper, more varied or better for my goals: staple foods of other kinds than the ones the pool has (grains, legumes, vegetables, fruits, nuts and seeds, ...)."""


def pool_prompt(pool, reason):
    blocks = [daily_need_block(), menu_tips_block(), food_pool_block(pool), food_manual_block()]
    tips = "Follow my goals and tips of menu_tips.txt.\n" if menu_tips_block() else ""
    wishes = menu_option_note("The foods must suit these wishes:")
    return "\n\n".join(block for block in blocks if block) + "\n\n" + (
        POOL_PROMPT.replace("{reason}", reason).replace("{wishes}", wishes).replace("{tips}", tips)
    )


if __name__ == "__main__":
    # 1. The wishes and the changes of the daily needs, as at step 1.0, then the foods of the pool that can be counted
    ask_menu_options()
    options = load_menu_options()
    pool = start_food_pool()
    descriptions = load_all_foods()
    units = load_food_units()
    limits = load_food_limits()
    forced = {fdc_id for fdc_id, _ in options.get("include", [])}
    missing = [descriptions[fdc_id] for fdc_id in forced if fdc_id not in pool]
    if missing:
        raise ValueError(
            f"Those foods the menu must have are not in {FOOD_POOL_FILE.name}: add a row for each one there, and its max "
            f"in {FOOD_LIMIT_FILE.name}, or remove them from the foods the menu must have: {', '.join(missing)}."
        )
    left_out = {fdc_id for fdc_id, _ in options.get("exclude", [])}
    generic_db = load_food_nutrients(set(pool))
    usable = []
    for fdc_id in pool:
        why = (
            "the menu must not have it" if fdc_id in left_out
            else "it has no nutrient" if fdc_id not in generic_db
            else f"it has no max in {FOOD_LIMIT_FILE.name}" if limits.get(fdc_id, (None, None))[1] is None
            else ""
        )
        if why:
            print(f"'{descriptions[fdc_id]}' is left out: {why}.")
        else:
            usable.append(fdc_id)
    if not usable:
        raise ValueError(f"No food of {FOOD_POOL_FILE.name} can be counted.")
    foods = [(fdc_id, units.get(fdc_id, GRAM)) for fdc_id in usable]
    units = dict(foods)

    # 2. A food is counted as its product, as in the report. One without price is counted at the price of the half
    # of the foods of its unit
    choices = choose_menu_products(usable)
    nutrient_db, _ = product_nutrient_db({fdc_id: generic_db[fdc_id] for fdc_id in usable}, choices)
    products = load_products()
    prices = {}
    for fdc_id in usable:
        product = products.get(choices.get(fdc_id), {})
        if product.get("price") is not None and product.get("package_amount"):
            prices[fdc_id] = product["price"] / product["package_amount"]
    known = set(prices)
    for fdc_id, unit in foods:
        of_unit = [prices[other] for other in known if units[other] == unit]
        prices.setdefault(fdc_id, statistics.median(of_unit) if of_unit else 0)
    print(f"{len(usable)} foods of the pool are counted, {len(known)} of them with the price of their product.")

    daily_needs = load_daily_needs()
    others = []
    saved = [{int(row[0]) for row in rows} for _, _, _, rows, _, _ in load_successful_menus().values()]
    if saved and ask_yes_no(f"Must the menu lack at least {DIFFERENT} foods of each saved menu", False):
        others = saved

    # 3. The cheapest menu. The needs that can be judged depend on its foods (see judged_needs): it is computed again
    # while they change
    needs = judged_needs(nutrient_db, daily_needs)
    amounts = None
    print("Computing the menu...")
    for _ in range(4):
        amounts = solve_menu(foods, nutrient_db, needs, limits, prices, forced, others)
        if amounts is None:
            break
        of_menu = judged_needs({fdc_id: nutrient_db[fdc_id] for fdc_id in amounts}, daily_needs)
        if [need["name"] for need in of_menu] == [need["name"] for need in needs]:
            break
        needs = of_menu

    reason = MORE_REASON
    if amounts is None:
        # 4. No menu: the closest one tells the needs that the pool lacks foods for
        closest = solve_menu(foods, nutrient_db, needs, limits, prices, forced, others, strict=False)
        if closest is None:
            raise ValueError("No menu could be computed from the pool.")
        unmet = [
            f"- {need['name']} ({need['unit']}): {total:.4g}, for {need['min']:g} to {'no limit' if need['max'] is None else f'{need['max']:g}'}"
            for need, total in zip(needs, day_totals(closest, units, nutrient_db, needs))
            if total < need["min"] or (need["max"] is not None and total > need["max"])
        ]
        print("No menu of the foods of the pool satisfies the daily needs. With the closest one, these needs are out:")
        print("\n".join(unmet))
        reason = UNMET_REASON.format(unmet="\n".join(unmet))
    else:
        price = sum(prices[fdc_id] * amount for fdc_id, amount in amounts.items())
        assumed = [descriptions[fdc_id] for fdc_id in amounts if fdc_id not in known]
        print(f"\nThe cheapest menu of the pool that satisfies the daily needs has {len(amounts)} foods:")
        for fdc_id, amount in amounts.items():
            print(f"{amount:>7g} {units[fdc_id]:<5}{descriptions[fdc_id]}" + ("" if fdc_id in known else "  (no price)"))
        print(
            f"Price of the day: {price:.2f} euros" + (
                f", {len(assumed)} foods without price being counted at the price of the half of the foods." if assumed else "."
            )
        )
        print(f"A food of the menu is counted {FOOD_COST:g} euros more than its price: a menu of few foods is preferred.")
        if not ask_yes_no("Ask the LLM for other foods for the pool instead of taking this menu", False):
            # 5. The menu is the one of menu.csv from now on. It has no text yet: step 6.0 asks the LLM for it
            save_menu([[str(fdc_id), descriptions[fdc_id], f"{amount:g}", units[fdc_id]] for fdc_id, amount in amounts.items()])
            save_menu_description("")
            # Not an error: exiting this way tells 0_run_all that there is nothing to ask the LLM
            sys.exit(
                f"The menu is in '{MENU_FILE}'. Go on with 5.0_get_product_prompt, which asks for the products of its "
                "foods that have none, then with 6.0_get_report, which asks for its text."
            )

    set_clipboard(pool_prompt(usable, reason))
    print("Paste it in a new discussion, copy the csv of the foods, then run 0.5_copy_pool.")
