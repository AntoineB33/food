import sys

import pandas as pd

# ---------------------------------------------------------
# 1. Load USDA SR Legacy CSVs + Manual CSVs
# ---------------------------------------------------------
print("Loading USDA and custom manual files...")

try:
    # Load standard SR Legacy files
    food_df = pd.read_csv("food.csv", usecols=["fdc_id", "description"])
    food_nutrient_df = pd.read_csv("food_nutrient.csv", usecols=["fdc_id", "nutrient_id", "amount"])

    # Load custom manual files
    food_manual_df = pd.read_csv("food_manual.csv", usecols=["fdc_id", "description"])
    food_nutrient_manual_df = pd.read_csv("food_nutrient_manual.csv", usecols=["fdc_id", "nutrient_id", "amount"])
    
except FileNotFoundError:
    print("Warning: Missing USDA CSV files. Ensure food.csv, food_manual.csv, etc., are in the directory.")
    sys.exit()

# Combine datasets
food_combined = pd.concat([food_df, food_manual_df], ignore_index=True)
food_nutrient_combined = pd.concat([food_nutrient_df, food_nutrient_manual_df], ignore_index=True)

# ---------------------------------------------------------
# 2. Filter Databases
# ---------------------------------------------------------
VEGAN_KEYWORDS = [
    "Tofu, firm", "Soybeans, mature cooked", "Lentils, mature seeds, cooked",
    "Beans, black, mature seeds, cooked", "Chickpeas, mature seeds, cooked",
    "Oats", "Rice, brown, long-grain, cooked", "Rice, white, long-grain, regular, cooked",
    "Peanuts, all types, raw", "Seeds, chia seeds", "Seeds, flaxseed",
    "Nuts, walnuts, English", "Broccoli, cooked", "Spinach, cooked", "Kale, cooked",
    "Sweet potato, cooked, baked", "Salt, table", "vegan" 
]

print("Filtering foods...")
# Match food descriptions
pattern = "|".join(VEGAN_KEYWORDS)
food_filtered = food_combined[food_combined["description"].str.contains(pattern, case=False, na=False)].copy()

# Filter nutrients to only those associated with our filtered foods to save space and processing time
food_nutrient_filtered = food_nutrient_combined[food_nutrient_combined["fdc_id"].isin(food_filtered["fdc_id"])].copy()

# ---------------------------------------------------------
# 3. Export Merged & Filtered Databases
# ---------------------------------------------------------
food_filtered.to_csv("food_filtered.csv", index=False)
food_nutrient_filtered.to_csv("food_nutrient_filtered.csv", index=False)

print(f"Success! Created filtered databases containing {len(food_filtered)} foods.")