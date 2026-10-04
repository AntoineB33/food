from common import (
    FOOD_NUTRIENT_HEADER,
    FOOD_NUTRIENT_MANUAL_FILE,
    FOOD_QTT_PROMPT,
    append_csv_rows,
    confirm,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_nutrient_csv,
    read_csv,
    set_clipboard,
)


def append_to_nutrient_manual(rows):
    """Appends the validated nutrient rows to food_nutrient_manual.csv."""
    existing = read_csv(FOOD_NUTRIENT_MANUAL_FILE)[1] if FOOD_NUTRIENT_MANUAL_FILE.exists() else []

    known = {(row[1], row[2]) for row in existing}
    for row in rows:
        if (row[1], row[2]) in known:
            raise ValueError(
                f"Nutrient {row[2]} of the food {row[1]} is already in '{FOOD_NUTRIENT_MANUAL_FILE}'. "
                "Was this clipboard text already appended?"
            )

    # The IDs chosen by the LLM may already be used: renumber after the last one of the file
    next_id = max((int(row[0]) for row in existing), default=49999) + 1
    rows = [[next_id + i, *row[1:]] for i, row in enumerate(rows)]

    append_csv_rows(FOOD_NUTRIENT_MANUAL_FILE, FOOD_NUTRIENT_HEADER, rows)
    print(f"Successfully appended {len(rows)} nutrient records to '{FOOD_NUTRIENT_MANUAL_FILE}'.")


if __name__ == "__main__":
    foods = load_food_manual()

    # 1. Get the checked nutrient csv (steps 3.0 and 3.5) from the clipboard
    clipboard_content = get_clipboard()

    print("\n" + "=" * 40)
    print("CURRENT CLIPBOARD TEXT:")
    print("=" * 40)
    print(clipboard_content)
    print("=" * 40 + "\n")

    # 2. Strictly validate it and append it to food_nutrient_manual.csv
    if confirm("Do you want to process and append the above clipboard text?"):
        append_to_nutrient_manual(parse_food_nutrient_csv(clipboard_content, {fdc_id for fdc_id, _ in foods}))
    else:
        print("Skipping clipboard text processing...")

    # 3. Generate the next prompt
    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n{FOOD_QTT_PROMPT}")
