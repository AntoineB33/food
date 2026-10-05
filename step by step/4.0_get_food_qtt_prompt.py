from common import (
    FOOD_NUTRIENT_HEADER,
    FOOD_NUTRIENT_MANUAL_FILE,
    FOOD_QTT_PROMPT,
    check_header,
    confirm,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_nutrient_csv,
    read_csv,
    set_clipboard,
    write_csv,
)


def save_to_nutrient_manual(rows):
    """Writes the validated nutrient rows to food_nutrient_manual.csv, replacing the rows of the same foods."""
    existing = []
    if FOOD_NUTRIENT_MANUAL_FILE.exists():
        header, existing = read_csv(FOOD_NUTRIENT_MANUAL_FILE)
        check_header(header, FOOD_NUTRIENT_HEADER, FOOD_NUTRIENT_MANUAL_FILE)

    # A food given again is replaced as a whole, so that none of its old rows remains
    new_foods = {row[1] for row in rows}
    kept = [row for row in existing if row[1] not in new_foods]
    replaced = sorted({int(row[1]) for row in existing if row[1] in new_foods})
    if replaced:
        print(f"Replacing the {len(existing) - len(kept)} existing nutrient records of the foods {replaced}.")

    # The IDs chosen by the LLM may already be used: renumber after the last one of the file
    next_id = max((int(row[0]) for row in existing), default=49999) + 1
    rows = [[next_id + i, *row[1:]] for i, row in enumerate(rows)]

    write_csv(FOOD_NUTRIENT_MANUAL_FILE, FOOD_NUTRIENT_HEADER, kept + rows)
    print(f"Successfully wrote {len(rows)} nutrient records to '{FOOD_NUTRIENT_MANUAL_FILE}'.")


if __name__ == "__main__":
    foods = load_food_manual()

    # 1. Get the checked nutrient csv (steps 3.0 and 3.5) from the clipboard
    clipboard_content = get_clipboard()

    print("\n" + "=" * 40)
    print("CURRENT CLIPBOARD TEXT:")
    print("=" * 40)
    print(clipboard_content)
    print("=" * 40 + "\n")

    # 2. Strictly validate it and write it to food_nutrient_manual.csv
    if confirm("Do you want to process and save the above clipboard text?"):
        save_to_nutrient_manual(parse_food_nutrient_csv(clipboard_content, {fdc_id for fdc_id, _ in foods}))
    else:
        print("Skipping clipboard text processing...")

    # 3. Generate the next prompt
    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(foods)}\n\n{FOOD_QTT_PROMPT}")
