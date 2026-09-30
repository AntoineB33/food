import sys

import pandas as pd

if len(sys.argv) < 2:
    print("Usage: python analyzer.py <diet_csv_file>")
    sys.exit(1)

input_file = sys.argv[1]

# ---------------------------------------------------------
# 1. Target Nutrients & Bounds (From Solver)
# ---------------------------------------------------------
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

bounds = {
    "calories": (2350, 2550), "protein": (150, 180), "fat": (65, 85),
    "carbs": (240, 310), "fiber": (34, 65), "omega_3": (1.6, 4.0),
    "omega_6": (11.0, 20.0), "leucine": (3.0, 6.0), "lysine": (2.3, 5.0),
    "valine": (2.0, 5.0), "isoleucine": (1.53, 4.0), "threonine": (1.15, 3.0),
    "histidine": (0.766, 2.0), "tryptophan": (0.306, 1.0),
    "vitamin_a": (900, 3000), "vitamin_c": (90, 2000), "vitamin_e": (15, 1000),
    "vitamin_k": (120, 1000), "vitamin_b1": (1.2, 9999), "vitamin_b2": (1.5, 9999),
    "vitamin_b3": (16.2, 35.0), "vitamin_b5": (5.0, 9999), "vitamin_b6": (1.3, 100),
    "vitamin_b9": (400, 1000), "iron": (14.4, 45.0), "zinc": (16.5, 40.0),
    "calcium": (1000, 2500), "magnesium": (400, 1000), "potassium": (3400, 6000),
    "sodium": (1500, 3000), "copper": (0.9, 10.0), "manganese": (2.3, 11.0),
    "phosphorus": (700, 4000), "choline": (550, 3500)
}

compound_bounds = {
    "phe_tyr": (1.915, 5.0),
    "met_cys": (1.15, 3.0) 
}

# ---------------------------------------------------------
# 2. Load Databases & User Input
# ---------------------------------------------------------
try:
    food_nutrient_df = pd.read_csv("food_nutrient_filtered.csv")
    diet_df = pd.read_csv(input_file)
except FileNotFoundError as e:
    print(f"Error loading file: {e}")
    sys.exit(1)

# Ensure required columns exist
if "fdc_id" not in diet_df.columns or "quantity_g" not in diet_df.columns:
    print("Input CSV must contain 'fdc_id' and 'quantity_g' columns.")
    sys.exit(1)

# ---------------------------------------------------------
# 3. Calculate Total Nutrients
# ---------------------------------------------------------
# Merge diet with nutrient values
merged = diet_df.merge(food_nutrient_df, on="fdc_id", how="inner")
merged = merged[merged["nutrient_id"].isin(TARGET_NUTRIENTS.keys())].copy()

# Map nutrient IDs to names and calculate totals (database amounts are per 100g)
merged["nutrient_name"] = merged["nutrient_id"].map(TARGET_NUTRIENTS)
merged["total_amount"] = merged["amount"] * (merged["quantity_g"] / 100.0)

# Aggregate totals
totals = merged.groupby("nutrient_name")["total_amount"].sum().to_dict()

# Add compound amino acids
totals["phe_tyr"] = totals.get("phenylalanine", 0) + totals.get("tyrosine", 0)
totals["met_cys"] = totals.get("methionine", 0) + totals.get("cysteine", 0)

# Merge bounds for iteration
all_bounds = {**bounds, **compound_bounds}

# ---------------------------------------------------------
# 4. Evaluate against Bounds
# ---------------------------------------------------------
lacking = {}
saturated = {}

for nutrient, (min_val, max_val) in all_bounds.items():
    amount = totals.get(nutrient, 0.0)
    
    if amount < min_val:
        lacking[nutrient] = (amount, min_val)
    elif amount > max_val and max_val != 9999:
        saturated[nutrient] = (amount, max_val)

# ---------------------------------------------------------
# 5. Display Results
# ---------------------------------------------------------
print(f"\n--- NUTRITION ANALYSIS FOR {input_file} ---")

print("\n🚨 LACKING NUTRIENTS (Below Minimum):")
if not lacking:
    print("  None! All minimum targets met.")
else:
    for nut, (amt, req) in sorted(lacking.items()):
        print(f"  - {nut.capitalize():<15} {amt:>7.1f} (Target: ≥ {req})")

print("\n⚠️ SATURATED NUTRIENTS (Exceeded Maximum):")
if not saturated:
    print("  None! All upper limits respected.")
else:
    for nut, (amt, limit) in sorted(saturated.items()):
        print(f"  - {nut.capitalize():<15} {amt:>7.1f} (Limit: ≤ {limit})")