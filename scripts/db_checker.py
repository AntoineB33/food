import sys
from pathlib import Path

import pandas as pd

DB_DIR = Path(__file__).resolve().parents[1] / "DB"

print("Loading USDA and custom manual files for nutrient audit...")

# ---------------------------------------------------------
# 1. Load Data
# ---------------------------------------------------------
try:
    food_df = pd.read_csv(DB_DIR / "food.csv", usecols=["fdc_id", "description"])
    food_nutrient_df = pd.read_csv(DB_DIR / "food_nutrient.csv", usecols=["fdc_id", "nutrient_id", "amount"])
    food_manual_df = pd.read_csv(DB_DIR / "food_manual.csv", usecols=["fdc_id", "description"])
    food_nutrient_manual_df = pd.read_csv(DB_DIR / "food_nutrient_manual.csv", usecols=["fdc_id", "nutrient_id", "amount"])
except FileNotFoundError as e:
    print(f"Error loading files: {e}\nPlease ensure all CSV files are in the current directory.")
    sys.exit(1)

# Combine datasets
food_df = pd.concat([food_df, food_manual_df], ignore_index=True)
food_nutrient_df = pd.concat([food_nutrient_df, food_nutrient_manual_df], ignore_index=True)

# ---------------------------------------------------------
# 2. Define Targets & Filter
# ---------------------------------------------------------
TARGET_NUTRIENTS = {
    1008: "calories",
    1003: "protein",
    1004: "fat",
    1005: "carbs",
    1079: "fiber",
    1093: "sodium",
    1215: "leucine"
}

VEGAN_KEYWORDS = [
    "Tofu, firm", "Soybeans, mature cooked", "Lentils, mature seeds, cooked",
    "Beans, black, mature seeds, cooked", "Chickpeas, mature seeds, cooked",
    "Oats", "Rice, brown, long-grain, cooked", "Rice, white, long-grain, regular, cooked",
    "Peanuts, all types, raw", "Seeds, chia seeds", "Seeds, flaxseed",
    "Nuts, walnuts, English", "Broccoli, cooked", "Spinach, cooked",
    "Sweet potato, cooked, baked", "Salt, table", "vegan"
]

# Filter foods based on keywords
pattern = "|".join(VEGAN_KEYWORDS)
filtered_foods = food_df[food_df["description"].str.contains(pattern, case=False, na=False)].copy()

# Filter nutrient records down to just our targets
target_nutrients_df = food_nutrient_df[food_nutrient_df["nutrient_id"].isin(TARGET_NUTRIENTS.keys())].copy()
target_nutrients_df["nutrient_name"] = target_nutrients_df["nutrient_id"].map(TARGET_NUTRIENTS)

# Left merge to ensure we keep foods even if they have ZERO nutrient records
merged = filtered_foods.merge(target_nutrients_df, on="fdc_id", how="left")

# ---------------------------------------------------------
# 3. Pivot and Audit for Missing Values
# ---------------------------------------------------------
# Pivot without a fill_value so missing records become NaN
db = merged.pivot_table(index="description", columns="nutrient_name", values="amount")

# Ensure all target nutrients exist as columns (in case a nutrient is missing across the entire dataset)
expected_columns = list(TARGET_NUTRIENTS.values())
for col in expected_columns:
    if col not in db.columns:
        db[col] = pd.NA

# Reorder columns for readability
db = db[expected_columns]

# Find rows where at least one nutrient is NaN
missing_data = db[db.isna().any(axis=1)]

# ---------------------------------------------------------
# 4. Report Results
# ---------------------------------------------------------
print(f"Auditing {len(db)} candidate ingredients...\n")

if missing_data.empty:
    print("✅ SUCCESS: Every selected food has a recorded value for every target nutrient.")
else:
    print(f"⚠️ WARNING: Found {len(missing_data)} food(s) with missing nutrient data:\n")
    
    for food_name, row in missing_data.iterrows():
        # Extract the names of the columns that are NaN for this specific food
        missing_nutrients = row[row.isna()].index.tolist()
        print(f"- {str(food_name)[:60]}")
        print(f"  Missing: {', '.join(missing_nutrients)}\n")
        
    print("Note: In your solver script, these were being filled with 0.0 automatically.")