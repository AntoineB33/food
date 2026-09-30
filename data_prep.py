import pandas as pd
import json

print("Loading USDA and custom manual files...")

# Load standard SR Legacy files
try:
    food_df = pd.read_csv("food.csv", usecols=["fdc_id", "description"])
    nutrient_df = pd.read_csv("nutrient.csv", usecols=["id", "name", "unit_name"])
    food_nutrient_df = pd.read_csv("food_nutrient.csv", usecols=["fdc_id", "nutrient_id", "amount"])

    # Load custom manual files
    food_manual_df = pd.read_csv("food_manual.csv", usecols=["fdc_id", "description"])
    food_nutrient_manual_df = pd.read_csv("food_nutrient_manual.csv", usecols=["fdc_id", "nutrient_id", "amount"])

    # Combine datasets
    food_df = pd.concat([food_df, food_manual_df], ignore_index=True)
    food_nutrient_df = pd.concat([food_nutrient_df, food_nutrient_manual_df], ignore_index=True)
except FileNotFoundError:
    print("Warning: Missing USDA CSV files. Ensure food.csv, nutrient.csv, etc., are in the directory.")
    exit()

# Target Nutrient IDs in USDA FoodData Central mapped to code variables
TARGET_NUTRIENTS = {
    1008: "calories", 1003: "protein", 1004: "fat", 1005: "carbs", 1079: "fiber",
    1270: "omega_3", 1269: "omega_6", 
    1215: "leucine", 1214: "lysine", 1219: "valine", 1213: "isoleucine",
    1217: "phenylalanine", 1218: "tyrosine", 1216: "methionine", 1226: "cysteine",
    1212: "threonine", 1221: "histidine", 1211: "tryptophan",
    1106: "vitamin_a", 1162: "vitamin_c", 1109: "vitamin_e", 1185: "vitamin_k",
    1165: "vitamin_b1", 1166: "vitamin_b2", 1167: "vitamin_b3", 1170: "vitamin_b5",
    1175: "vitamin_b6", 1190: "vitamin_b9",
    1089: "iron", 1095: "zinc", 1087: "calcium", 1090: "magnesium", 1092: "potassium",
    1093: "sodium", 1098: "copper", 1101: "manganese", 1091: "phosphorus",
    1186: "choline"
}

VEGAN_KEYWORDS = [
    "Tofu, firm", "Soybeans, mature cooked", "Lentils, mature seeds, cooked",
    "Beans, black, mature seeds, cooked", "Chickpeas, mature seeds, cooked",
    "Oats", "Rice, brown, long-grain, cooked", "Rice, white, long-grain, regular, cooked",
    "Peanuts, all types, raw", "Seeds, chia seeds", "Seeds, flaxseed",
    "Nuts, walnuts, English", "Broccoli, cooked", "Spinach, cooked", "Kale, cooked",
    "Sweet potato, cooked, baked", "Salt, table", "vegan" 
]

# Match food descriptions
pattern = "|".join(VEGAN_KEYWORDS)
filtered_foods = food_df[food_df["description"].str.contains(pattern, case=False, na=False)].copy()

# Join with nutrient values
merged = filtered_foods.merge(food_nutrient_df, on="fdc_id")
merged = merged[merged["nutrient_id"].isin(TARGET_NUTRIENTS.keys())]
merged["nutrient_name"] = merged["nutrient_id"].map(TARGET_NUTRIENTS)

# Pivot so rows = Food, columns = Nutrients (values are per 100g)
db = merged.pivot_table(index="description", columns="nutrient_name", values="amount", fill_value=0).reset_index()

# Convert to dictionary
foods_raw = db.set_index("description").to_dict(orient="index")
foods = {
    str(description): {str(key): float(value) for key, value in row.items()}
    for description, row in foods_raw.items()
}

print(f"Extracted {len(foods)} candidate ingredients.\n")

# Save the compiled dictionary to a JSON file for the solver
with open("processed_foods.json", "w") as f:
    json.dump(foods, f, indent=4)
print("Data successfully saved to 'processed_foods.json'.")