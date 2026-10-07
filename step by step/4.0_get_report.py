from collections import defaultdict

from common import (
    DOSE,
    file_block,
    load_all_foods,
    load_daily_needs,
    load_food_nutrients,
    load_identified_menu,
    rows_to_csv,
    set_clipboard,
)

PROMPT = "Adjust the menu to fix these lacks and excesses."


def build_report(daily_needs, daily_totals, nutrient_db):
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

    if lacks or excesses:
        report_lines.append(PROMPT)
    else:
        print("No nutrition lacks or excesses found. The diet matches the daily needs!")
    return "\n".join(report_lines).strip()


if __name__ == "__main__":
    # 1. The menu saved and checked at step 2.5, an ingredient being possibly given several times
    menu = load_identified_menu()
    nutrient_db = load_food_nutrients({fdc_id for fdc_id, _, _ in menu})
    descriptions = load_all_foods()
    without_nutrient = [
        f"{fdc_id} ({descriptions[fdc_id]})" for fdc_id in dict.fromkeys(fdc_id for fdc_id, _, _ in menu)
        if fdc_id not in nutrient_db
    ]
    if without_nutrient:
        raise ValueError(f"No nutrient for the foods, run steps 3.0 and 3.5 first: {', '.join(without_nutrient)}.")

    # 2. Sum the nutrients of the whole menu: they are given for 100g of a food, or for one dose of a supplement
    daily_totals = defaultdict(float)
    for fdc_id, amount, unit in menu:
        for nutrient_id, nutrient_amount in nutrient_db[fdc_id].items():
            daily_totals[nutrient_id] += nutrient_amount * (amount if unit == DOSE else amount / 100)

    # 3. Compare them with the daily needs. The foods are shown, so that Gemini sees what was counted.
    counted = [[fdc_id, descriptions[fdc_id], f"{amount:g}", unit] for fdc_id, amount, unit in menu]
    final_report = (
        f"{file_block('Foods counted for the day', rows_to_csv(['fdc_id', 'description', 'amount', 'unit'], counted))}\n\n"
        f"{build_report(load_daily_needs(), daily_totals, nutrient_db)}"
    )
    print("\nPreview:\n" + "=" * 40)
    print(final_report)
    print("=" * 40)
    set_clipboard(final_report)
