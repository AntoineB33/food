from common import (
    FOOD_QTT_PROMPT,
    confirm,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_food_nutrient_csv,
    save_to_nutrient_manual,
    set_clipboard,
)


if __name__ == "__main__":
    foods = load_food_manual()

    # 1. Get the checked nutrient csv (step 2.7) from the clipboard
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
