from collections import defaultdict
from datetime import date

from common import (
    DOSE,
    MENU_NOTE,
    MENU_OPTION_KEEP_INTRO,
    daily_need_block,
    load_all_foods,
    load_daily_needs,
    load_food_nutrients,
    load_identified_menu,
    load_menu,
    menu_block,
    menu_option_note,
    save_successful_menu,
    set_clipboard,
)

PROMPT = f"""The table above is my vegan menu for a day, fdc_description being the food of SR Legacy 2018 or of my own foods that each row was counted as. The report compares its total for the day with daily_need_table.csv.
Correct the menu to fix these lacks and excesses, without creating new ones.
{menu_option_note(MENU_OPTION_KEEP_INTRO)}{MENU_NOTE}
- Keep the description of the foods you keep unchanged, even when you change their amount."""


def build_report(daily_needs, daily_totals, nutrient_db):
    """Returns the report, and whether the menu satisfies the daily needs."""
    lacks, excesses, on_target, unknown = [], [], [], []
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
        elif need["max"] is not None and total > need["max"]:
            excesses.append(record)
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
    return "\n".join(report_lines).strip(), not (lacks or excesses)


if __name__ == "__main__":
    # 1. The menu identified at step 2.5, whose new foods got their nutrients at steps 3.5 and 4.0
    menu = load_identified_menu()
    nutrient_db = load_food_nutrients({fdc_id for fdc_id, _, _ in menu})
    descriptions = load_all_foods()
    without_nutrient = [f"{fdc_id} ({descriptions[fdc_id]})" for fdc_id, _, _ in menu if fdc_id not in nutrient_db]
    if without_nutrient:
        raise ValueError(f"No nutrient for the foods, run steps 3.0 to 4.0 first: {', '.join(without_nutrient)}.")

    # 2. Sum the nutrients of the whole menu: they are given for 100g of a food, or for one dose of a supplement
    daily_totals = defaultdict(float)
    for fdc_id, amount, unit in menu:
        for nutrient_id, nutrient_amount in nutrient_db[fdc_id].items():
            daily_totals[nutrient_id] += nutrient_amount * (amount if unit == DOSE else amount / 100)

    # 3. Compare them with the daily needs
    report, satisfied = build_report(load_daily_needs(), daily_totals, nutrient_db)
    print("\n" + "=" * 40)
    print(report)
    print("=" * 40)
    if satisfied:
        print("No nutrition lacks or excesses found. The menu satisfies the daily needs!")
        save_successful_menu(load_menu(), date.today().isoformat())
    else:
        set_clipboard(f"{daily_need_block()}\n\n{menu_block(load_menu(), descriptions)}\n\n{report}\n\n{PROMPT}")
        print("Paste it in a new discussion, copy the csv of the corrected menu, run 1.5_copy_menu_then_check to save it, then go on from 2.0_get_food_prompt.")
