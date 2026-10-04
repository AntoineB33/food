from common import LAST_CHECKED_FILE, load_food_manual

if __name__ == "__main__":
    # Every food of food_manual.csv is now checked: remember the last one
    foods = load_food_manual()
    if not foods:
        raise ValueError("food_manual.csv contains no data rows.")

    description = foods[-1][1]
    LAST_CHECKED_FILE.write_text(description, encoding="utf-8")
    print(f"Successfully wrote '{description}' to {LAST_CHECKED_FILE}")
