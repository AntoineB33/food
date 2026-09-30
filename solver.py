import sys

import pandas as pd
import pulp

# ---------------------------------------------------------
# 1. Load Filtered Databases & Nutrient Mappings
# ---------------------------------------------------------
print("Loading filtered databases...")

try:
    # Load the databases created by the first program, plus nutrient.csv
    food_df = pd.read_csv("food_filtered.csv")
    food_nutrient_df = pd.read_csv("food_nutrient_filtered.csv")
    nutrient_df = pd.read_csv("nutrient.csv", usecols=["id", "name", "unit_name"])
except FileNotFoundError:
    print("Warning: Missing required CSV files. Ensure you have run the database creation script first.")
    sys.exit()

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

# ---------------------------------------------------------
# 2. Define Solver Bounds (Daily Targets)
# ---------------------------------------------------------
bounds = {
    "calories": (2350, 2550),
    "protein": (150, 180),
    "fat": (65, 85),
    "carbs": (240, 310),
    "fiber": (34, 65),
    "omega_3": (1.6, 4.0),
    "omega_6": (11.0, 20.0),
    "leucine": (3.0, 6.0),
    "lysine": (2.3, 5.0),
    "valine": (2.0, 5.0),
    "isoleucine": (1.53, 4.0),
    "threonine": (1.15, 3.0),
    "histidine": (0.766, 2.0),
    "tryptophan": (0.306, 1.0),
    "vitamin_a": (900, 3000),
    "vitamin_c": (90, 2000),
    "vitamin_e": (15, 1000),
    "vitamin_k": (120, 1000),
    "vitamin_b1": (1.2, 9999), 
    "vitamin_b2": (1.5, 9999),
    "vitamin_b3": (16.2, 35.0),
    "vitamin_b5": (5.0, 9999),
    "vitamin_b6": (1.3, 100),
    "vitamin_b9": (400, 1000),
    "iron": (14.4, 45.0),
    "zinc": (16.5, 40.0),
    "calcium": (1000, 2500),
    "magnesium": (400, 1000),
    "potassium": (3400, 6000),
    "sodium": (1500, 3000),
    "copper": (0.9, 10.0),    
    "manganese": (2.3, 11.0),
    "phosphorus": (700, 4000),
    "choline": (550, 3500)
}

compound_bounds = {
    "phe_tyr": (1.915, 5.0), # Phenylalanine + Tyrosine
    "met_cys": (1.15, 3.0)   # Methionine + Cysteine
}

# ---------------------------------------------------------
# 3. Format Database for PuLP
# ---------------------------------------------------------
# Join with nutrient values
merged = food_df.merge(food_nutrient_df, on="fdc_id")
merged = merged[merged["nutrient_id"].isin(TARGET_NUTRIENTS.keys())]
merged["nutrient_name"] = merged["nutrient_id"].map(TARGET_NUTRIENTS)

# Pivot so rows = Food, columns = Nutrients (values are per 100g)
db = merged.pivot_table(index="description", columns="nutrient_name", values="amount", fill_value=0).reset_index()

# Convert to PuLP-friendly dictionary
foods_raw = db.set_index("description").to_dict(orient="index")
foods = {
    str(description): {str(key): float(value) for key, value in row.items()}
    for description, row in foods_raw.items()
}
print(f"Extracted {len(foods)} candidate ingredients.\n")

# ---------------------------------------------------------
# 4. Formulate the MILP Model
# ---------------------------------------------------------
prob = pulp.LpProblem("SR_Legacy_Vegan_Recomp", pulp.LpMinimize)

servings = {
    food: pulp.LpVariable(f"g_{i}", lowBound=0, upBound=6.0, cat="Continuous")
    for i, food in enumerate(foods)
}

# Culinary restriction overrides
for food in foods:
    if "Salt" in food:
        servings[food].upBound = 0.08
    if "Seeds, chia" in food or "flaxseed" in food:
        servings[food].upBound = 0.40

# Objective: Minimize Calories
prob += pulp.lpSum([foods[f].get("calories", 0) * servings[f] for f in foods]), "Minimize_Calories"

# Apply standard nutrient bounds
for nutrient, (min_val, max_val) in bounds.items():
    prob += pulp.lpSum([foods[f].get(nutrient, 0) * servings[f] for f in foods]) >= min_val, f"Min_{nutrient}"
    if max_val != 9999: # 9999 represents "No limit"
        prob += pulp.lpSum([foods[f].get(nutrient, 0) * servings[f] for f in foods]) <= max_val, f"Max_{nutrient}"

# Apply compound amino acid bounds
prob += pulp.lpSum([(foods[f].get("phenylalanine", 0) + foods[f].get("tyrosine", 0)) * servings[f] for f in foods]) >= compound_bounds["phe_tyr"][0], "Min_Phe_Tyr"
prob += pulp.lpSum([(foods[f].get("phenylalanine", 0) + foods[f].get("tyrosine", 0)) * servings[f] for f in foods]) <= compound_bounds["phe_tyr"][1], "Max_Phe_Tyr"

prob += pulp.lpSum([(foods[f].get("methionine", 0) + foods[f].get("cysteine", 0)) * servings[f] for f in foods]) >= compound_bounds["met_cys"][0], "Min_Met_Cys"
prob += pulp.lpSum([(foods[f].get("methionine", 0) + foods[f].get("cysteine", 0)) * servings[f] for f in foods]) <= compound_bounds["met_cys"][1], "Max_Met_Cys"

# ---------------------------------------------------------
# 5. Solve and Inspect
# ---------------------------------------------------------
prob.solve(pulp.PULP_CBC_CMD(msg=False))
print(f"Solver Status: {pulp.LpStatus[prob.status]}")

if prob.status == pulp.LpStatusOptimal:
    print("\n### Generated Daily Whole-Food Rations ###")
    for food in foods:
        val = servings[food].varValue
        if val and val > 0.05:  # Filter out amounts < 5g
            print(f"- {food[:60]}: {round(val * 100, 1)}g")

    print("\n### Target Validations ###")
    for nutrient in list(bounds.keys()):
        total = sum(foods[f].get(nutrient, 0) * (servings[f].varValue or 0.0) for f in foods)
        unit = "mg" if nutrient not in ["calories", "protein", "fat", "carbs", "fiber", "leucine", "lysine", "valine", "isoleucine", "threonine", "histidine", "tryptophan", "omega_3", "omega_6"] else "g"
        if nutrient == "calories": unit = "kcal"
        if nutrient in ["vitamin_a", "vitamin_k", "vitamin_b9"]: unit = "mcg"
        
        print(f"{nutrient.capitalize():<12}: {round(total, 1)} {unit}")
        
    print("\n### Supplement Action Items ###")
    print("- Algae Oil (EPA/DHA): 500-1,000 mg")
    print("- Vitamin D3 (Lichen): 600-4,000 IU")
    print("- Vitamin B12: ≥2.4 mcg")
    print("- Selenium: 1-2 Brazil Nuts")
    print("- Creatine Monohydrate: 3-5 g")
    print("- Hydration: 3.2 - 4.5 L Water")
else:
    print("Infeasible: The USDA dataset might lack sufficient data for some micronutrients or constraints are conflicting.")
    print("Try relaxing the Fiber max bound or adding fortified/custom foods to food_manual.csv.")