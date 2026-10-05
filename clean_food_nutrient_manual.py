"""Removes from food_nutrient_manual.csv the rows of the foods that are not in food_manual.csv."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "step by step"))

from common import (
    FOOD_MANUAL_FILE,
    FOOD_NUTRIENT_HEADER,
    FOOD_NUTRIENT_MANUAL_FILE,
    check_header,
    confirm,
    load_food_manual,
    read_csv,
    write_csv,
)

if __name__ == "__main__":
    existing_foods = {str(fdc_id) for fdc_id, _ in load_food_manual()}

    header, rows = read_csv(FOOD_NUTRIENT_MANUAL_FILE)
    check_header(header, FOOD_NUTRIENT_HEADER, FOOD_NUTRIENT_MANUAL_FILE)

    kept = [row for row in rows if row[1] in existing_foods]
    removed = Counter(row[1] for row in rows if row[1] not in existing_foods)

    if not removed:
        print(f"Nothing to remove: every food of {FOOD_NUTRIENT_MANUAL_FILE.name} is in {FOOD_MANUAL_FILE.name}.")
    else:
        print(f"Foods of {FOOD_NUTRIENT_MANUAL_FILE.name} that are not in {FOOD_MANUAL_FILE.name}:")
        for fdc_id, count in removed.items():
            print(f"- {fdc_id}: {count} rows")

        if confirm(f"Do you want to remove these {len(rows) - len(kept)} rows?"):
            write_csv(FOOD_NUTRIENT_MANUAL_FILE, FOOD_NUTRIENT_HEADER, kept)
            print(f"Successfully removed {len(rows) - len(kept)} rows, {len(kept)} rows kept.")
        else:
            print("Nothing removed.")
