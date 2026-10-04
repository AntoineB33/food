from collections import defaultdict

from common import (
    get_clipboard,
    load_daily_needs,
    load_diet_nutrients,
    parse_diet_csv,
    set_clipboard,
)

# Quantity of the clipboard csv corresponding to the 100g the nutrient amounts are given for
PORTION_DIVISOR = 1.0

PROMPT = "Adjust the menu to fix these lacks and excesses."


def build_report(daily_needs, daily_totals):
    lacks, excesses, on_target = [], [], []
    for need in daily_needs:
        # The needs without nutrient ID cannot be computed from the databases
        if not need["ids"]:
            continue
        total = sum(daily_totals[nutrient_id] for nutrient_id in need["ids"])
        max_str = "no limit" if need["max"] is None else f"{need['max']:g}"
        record = f"- **{need['name']}** ({need['unit']}): {total:.2f} (Target: {need['min']:g} to {max_str})"

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
    ):
        if records:
            report_lines += [f"#### {title}:", *records, ""]

    if lacks or excesses:
        report_lines.append(PROMPT)
    else:
        print("No nutrition lacks or excesses found. The diet matches the daily needs!")
    return "\n".join(report_lines).strip()


if __name__ == "__main__":
    # 1. Get the checked quantity csv (steps 4.0 and 4.5) from the clipboard
    diet = parse_diet_csv(get_clipboard())
    nutrient_db = load_diet_nutrients(diet)
    daily_needs = load_daily_needs()

    # 2. Sum the nutrients of the whole diet
    daily_totals = defaultdict(float)
    for fdc_id, quantity in diet.items():
        for nutrient_id, amount in nutrient_db[fdc_id].items():
            daily_totals[nutrient_id] += amount * quantity / PORTION_DIVISOR

    # 3. Compare them with the daily needs
    final_report = build_report(daily_needs, daily_totals)
    print("\nPreview:\n" + "=" * 40)
    print(final_report)
    print("=" * 40)
    set_clipboard(final_report)
