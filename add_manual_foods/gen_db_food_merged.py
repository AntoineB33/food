import sys
from pathlib import Path

import pandas as pd

DB_DIR = Path(__file__).resolve().parents[1] / "DB"

# ---------------------------------------------------------
# 1. Load USDA SR Legacy CSVs + Manual CSVs
# ---------------------------------------------------------
print("Loading USDA and custom manual files...")

try:
    # Load standard SR Legacy files
    food_df = pd.read_csv(DB_DIR / "food.csv", usecols=["fdc_id", "description"])
    food_nutrient_df = pd.read_csv(DB_DIR / "food_nutrient.csv", usecols=["fdc_id", "nutrient_id", "amount"])

    # Load custom manual files
    food_manual_df = pd.read_csv(DB_DIR / "food_manual.csv", usecols=["fdc_id", "description"])
    food_nutrient_manual_df = pd.read_csv(DB_DIR / "food_nutrient_manual.csv", usecols=["fdc_id", "nutrient_id", "amount"])

except FileNotFoundError:
    print("Warning: Missing CSV files. Ensure food.csv, food_manual.csv, etc., are in the DB directory.")
    sys.exit()

# Combine datasets
print("Merging databases...")
food_combined = pd.concat([food_df, food_manual_df], ignore_index=True)
food_nutrient_combined = pd.concat([food_nutrient_df, food_nutrient_manual_df], ignore_index=True)

# Note: The data_type drop was removed because using usecols=["fdc_id", "description"] 
# guarantees data_type is never loaded into the dataframe in the first place.

# ---------------------------------------------------------
# 2. Export Merged (Unfiltered) Databases
# ---------------------------------------------------------
print("Exporting to CSV...")
food_combined.to_csv(DB_DIR / "food_merged.csv", index=False)
food_nutrient_combined.to_csv(DB_DIR / "food_nutrient_merged.csv", index=False)

print(f"Success! Created merged, unfiltered databases containing {len(food_combined)} foods.")