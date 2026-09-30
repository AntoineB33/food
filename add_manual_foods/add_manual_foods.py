import os
from pathlib import Path

import pandas as pd

# Configuration: File paths
ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "DB"
TXT_FILE = Path(__file__).resolve().parent / "foods_to_add.txt"
FOOD_CSV = DB_DIR / "food.csv"
MANUAL_CSV = DB_DIR / "food_manual.csv"

def normalize_manual_csv():
    if not os.path.exists(MANUAL_CSV):
        return

    try:
        manual_df = pd.read_csv(MANUAL_CSV)
    except pd.errors.EmptyDataError:
        return

    if manual_df.empty:
        manual_df = pd.DataFrame(columns=["fdc_id", "description"])
    else:
        if "description" not in manual_df.columns:
            manual_df["description"] = ""
        if "data_type" in manual_df.columns:
            manual_df = manual_df.drop(columns=["data_type"])
        manual_df = manual_df[["fdc_id", "description"]]

    manual_df = manual_df.drop_duplicates(subset=["fdc_id"], keep="last")
    manual_df.to_csv(MANUAL_CSV, index=False)


def main():
    print("Loading existing databases to find available IDs...")
    existing_ids = set()
    existing_descriptions = set()
    normalize_manual_csv()

    # 1. Load standard SR Legacy food.csv
    try:
        food_df = pd.read_csv(FOOD_CSV, usecols=["fdc_id", "description"])
        existing_ids.update(pd.to_numeric(food_df["fdc_id"], errors="coerce").dropna().astype(int).tolist())
        existing_descriptions.update(food_df["description"].dropna().str.lower().tolist())
    except FileNotFoundError:
        print(f"Error: Missing '{FOOD_CSV}'. This is required to ensure IDs don't overlap.")
        return

    # 2. Load custom food_manual.csv (if it exists)
    if os.path.exists(MANUAL_CSV):
        try:
            manual_df = pd.read_csv(MANUAL_CSV, usecols=["fdc_id", "description"])
            existing_ids.update(pd.to_numeric(manual_df["fdc_id"], errors="coerce").dropna().astype(int).tolist())
            existing_descriptions.update(manual_df["description"].dropna().str.lower().tolist())
        except pd.errors.EmptyDataError:
            pass
    else:
        print(f"'{MANUAL_CSV}' not found. It will be created.")

    # Determine the starting point for new IDs
    current_max_id = max(existing_ids) if existing_ids else 2000000

    # 3. Read the text file containing foods to add
    if not os.path.exists(TXT_FILE):
        print(f"Error: Missing input file '{TXT_FILE}'. Please create it and add food descriptions, one per line.")
        return

    with open(TXT_FILE, "r", encoding="utf-8") as f:
        foods_to_add = [line.strip() for line in f if line.strip()]

    # 4. Generate new IDs for the new foods
    new_records = []
    for food in foods_to_add:
        if food.lower() in existing_descriptions:
            print(f"  - Skipping '{food}': already exists in a database.")
            continue

        current_max_id += 1
        new_records.append({"fdc_id": current_max_id, "description": food})
        existing_descriptions.add(food.lower())

    # 5. Append to food_manual.csv
    if not new_records:
        print("\nNo new foods were added.")
        return

    new_df = pd.DataFrame(new_records, columns=["fdc_id", "description"])
    file_exists = os.path.exists(MANUAL_CSV)
    if file_exists:
        existing_manual_df = pd.read_csv(MANUAL_CSV, usecols=["fdc_id", "description"])
        combined_df = pd.concat([existing_manual_df, new_df], ignore_index=True)
        combined_df = combined_df[["fdc_id", "description"]].drop_duplicates(subset=["fdc_id"], keep="last")
        combined_df.to_csv(MANUAL_CSV, index=False)
    else:
        new_df.to_csv(MANUAL_CSV, index=False)

    print(f"\nSuccess! Added {len(new_records)} new foods to '{MANUAL_CSV}'.")
    for record in new_records:
        print(f"  + ID: {record['fdc_id']} | {record['description']}")

if __name__ == "__main__":
    main()