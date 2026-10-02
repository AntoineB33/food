import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------
# Set your input CSV file name here
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR.parent / "DB"
input_file = BASE_DIR / "my_diet.csv"
output_file = BASE_DIR / f"{input_file.stem}_report.txt"

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
    food_nutrient_df = pd.read_csv(DB_DIR / "food_nutrient_filtered.csv")
    diet_df = pd.read_csv(input_file)
    food_df = pd.read_csv(DB_DIR / "food_filtered.csv")
    nutrient_df = pd.read_csv(DB_DIR / "nutrient.csv")
except FileNotFoundError as e:
    print(f"Error loading file: {e}")
    sys.exit(1)

diet_df = diet_df.rename(columns={"food_id": "fdc_id", "quantity": "quantity_g"})

# Ensure required columns exist
if "fdc_id" not in diet_df.columns or "quantity_g" not in diet_df.columns:
    print("Input CSV must contain 'fdc_id' and 'quantity_g' columns.")
    sys.exit(1)

diet_df["fdc_id"] = pd.to_numeric(diet_df["fdc_id"], errors="raise")
diet_df["quantity_g"] = pd.to_numeric(diet_df["quantity_g"], errors="raise")

# Ensure nutrient IDs can match
nutrient_df["id"] = pd.to_numeric(nutrient_df["id"], errors="coerce")

# ---------------------------------------------------------
# 3. Create Unit Mappings
# ---------------------------------------------------------
# Map raw nutrient IDs to their unit names (e.g. 1008 -> 'KCAL')
id_to_unit = dict(zip(nutrient_df["id"], nutrient_df["unit_name"]))

# Map our readable string names to unit names (e.g. 'calories' -> 'KCAL')
name_to_unit = {name: id_to_unit.get(nut_id, "g") for nut_id, name in TARGET_NUTRIENTS.items()}

# Add units for compound amino acids (they inherit from their base amino acids)
name_to_unit["phe_tyr"] = name_to_unit.get("phenylalanine", "g")
name_to_unit["met_cys"] = name_to_unit.get("methionine", "g")

# ---------------------------------------------------------
# 4. Calculate Total Nutrients
# ---------------------------------------------------------
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

all_bounds = {**bounds, **compound_bounds}

# ---------------------------------------------------------
# 5. Evaluate against Bounds
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
# 6. Generate Report (Console & Text File)
# ---------------------------------------------------------
report_lines = []
report_lines.append(f"--- NUTRITION ANALYSIS FOR {input_file.name} ---")

# Merge diet with food names to list out the meal plan
report_lines.append("\n🍽️ FOOD LIST:")
food_list = diet_df.merge(food_df, on="fdc_id", how="left")
for _, row in food_list.iterrows():
    desc = row.get("description", f"Unknown Food ID {row['fdc_id']}")
    qty = row['quantity_g']
    report_lines.append(f"  - {qty}g : {desc}")

# Lacking
report_lines.append("\n🚨 LACKING NUTRIENTS (Below Minimum):")
if not lacking:
    report_lines.append("  None! All minimum targets met.")
else:
    for nut, (amt, req) in sorted(lacking.items()):
        unit = name_to_unit.get(nut, "units")
        report_lines.append(f"  - {nut.capitalize():<15} {amt:>7.1f} {unit:<4} (Target: >= {req} {unit})")

# Saturated
report_lines.append("\n⚠️ SATURATED NUTRIENTS (Exceeded Maximum):")
if not saturated:
    report_lines.append("  None! All upper limits respected.")
else:
    for nut, (amt, limit) in sorted(saturated.items()):
        unit = name_to_unit.get(nut, "units")
        report_lines.append(f"  - {nut.capitalize():<15} {amt:>7.1f} {unit:<4} (Limit: <= {limit} {unit})")

# Join lines into a single string
final_report = "\n".join(report_lines)

# Print to console
print(final_report)

# Write to text file
with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_report)

print(f"\n✅ Report successfully saved to: {output_file.name}")