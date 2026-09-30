import pulp
import json
import sys

# Load pre-processed foods
print("Loading processed foods data...")
try:
    with open("processed_foods.json", "r") as f:
        foods = json.load(f)
except FileNotFoundError:
    print("Error: 'processed_foods.json' not found. Run data_prep.py first.")
    sys.exit()

# Define Solver Bounds (Daily Targets)
bounds = {
    "calories": (2350, 2550), "protein": (150, 180), "fat": (65, 85),
    "carbs": (240, 310), "fiber": (34, 65), "omega_3": (1.6, 4.0),
    "omega_6": (11.0, 20.0), "leucine": (3.0, 6.0), "lysine": (2.3, 5.0),
    "valine": (2.0, 5.0), "isoleucine": (1.53, 4.0), "threonine": (1.15, 3.0),
    "histidine": (0.766, 2.0), "tryptophan": (0.306, 1.0), "vitamin_a": (900, 3000),
    "vitamin_c": (90, 2000), "vitamin_e": (15, 1000), "vitamin_k": (120, 1000),
    "vitamin_b1": (1.2, 9999), "vitamin_b2": (1.5, 9999), "vitamin_b3": (16.2, 35.0),
    "vitamin_b5": (5.0, 9999), "vitamin_b6": (1.3, 100), "vitamin_b9": (400, 1000),
    "iron": (14.4, 45.0), "zinc": (16.5, 40.0), "calcium": (1000, 2500),
    "magnesium": (400, 1000), "potassium": (3400, 6000), "sodium": (1500, 3000),
    "copper": (0.9, 10.0), "manganese": (2.3, 11.0), "phosphorus": (700, 4000),
    "choline": (550, 3500)
}

# Compound amino acids
compound_bounds = {
    "phe_tyr": (1.915, 5.0), # Phenylalanine + Tyrosine
    "met_cys": (1.15, 3.0)   # Methionine + Cysteine
}

# Formulate the MILP Model
prob = pulp.LpProblem("SR_Legacy_Vegan_Recomp", pulp.LpMinimize)

servings = {
    food: pulp.LpVariable(f"g_{i}", lowBound=0, upBound=6.0, cat="Continuous")
    for i, food in enumerate(foods)
}

# Culinary restrictions
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

# Solve and Inspect
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