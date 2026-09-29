import pandas as pd
import pulp

# ---------------------------------------------------------
# 1. Load and Filter USDA SR Legacy CSVs
# ---------------------------------------------------------
print("Loading USDA files...")
food_df = pd.read_csv("food.csv", usecols=["fdc_id", "description"])
nutrient_df = pd.read_csv("nutrient.csv", usecols=["id", "name", "unit_name"])
food_nutrient_df = pd.read_csv("food_nutrient.csv", usecols=["fdc_id", "nutrient_id", "amount"])

# Target Nutrient IDs in USDA FoodData Central:
# 1008: Energy (kcal), 1003: Protein (g), 1004: Total Fat (g),
# 1005: Carbohydrate (g), 1079: Fiber (g), 1093: Sodium (mg), 1213: Leucine (g)
TARGET_NUTRIENTS = {
    1008: "calories",
    1003: "protein",
    1004: "fat",
    1005: "carbs",
    1079: "fiber",
    1093: "sodium",
    1213: "leucine"
}

# Curate a list of keywords to pull whole vegan ingredients (per 100g raw/cooked)
VEGAN_KEYWORDS = [
    "Tofu, firm", "Soybeans, mature cooked", "Lentils, mature seeds, cooked",
    "Beans, black, mature seeds, cooked", "Chickpeas, mature seeds, cooked",
    "Oats", "Rice, brown, long-grain, cooked", "Rice, white, long-grain, regular, cooked",
    "Peanuts, all types, raw", "Seeds, chia seeds", "Seeds, flaxseed",
    "Nuts, walnuts, English", "Broccoli, cooked", "Spinach, cooked",
    "Sweet potato, cooked, baked", "Salt, table"
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

# Convert to PuLP-friendly dictionary
foods_raw = db.set_index("description").to_dict(orient="index")
foods: dict[str, dict[str, float]] = {
    str(description): {str(key): float(value) for key, value in row.items()}
    for description, row in foods_raw.items()
}
print(f"Extracted {len(foods)} candidate ingredients from SR Legacy.\n")

# ---------------------------------------------------------
# 2. Define Solver Bounds (Daily Targets)
# ---------------------------------------------------------
bounds = {
    "calories": (2350, 2550),
    "protein": (150, 180),
    "fat": (65, 85),
    "carbs": (240, 310),
    "fiber": (34, 65),       # Prevents gut distress and phytic acid saturation
    "sodium": (1500, 3000),   # Met naturally + via table salt
    "leucine": (3.0, 8.0)     # USDA Leucine is in grams per 100g
}

# ---------------------------------------------------------
# 3. Formulate the MILP Model
# ---------------------------------------------------------
prob = pulp.LpProblem("SR_Legacy_Vegan_Recomp", pulp.LpMinimize)

# Decision variables: Number of 100g units (or 0.1 units = 10g for dense foods)
# Using continuous variables (cat='Continuous') with step increments is more realistic 
# than strict integers when measuring raw ingredients by weight.
servings = {
    food: pulp.LpVariable(f"g_{i}", lowBound=0, upBound=6.0, cat="Continuous")
    for i, food in enumerate(foods)
}

# Restrict table salt to reasonable culinary usage (max 0.08 x 100g = 8g salt)
for food in foods:
    if isinstance(food, str) and "Salt" in food:
        servings[food].upBound = 0.08

# Objective: Minimize total calories within the window
prob += pulp.lpSum([foods[f]["calories"] * servings[f] for f in foods]), "Minimize_Calories"

# Apply all nutrient bounds
for nutrient, (min_val, max_val) in bounds.items():
    prob += pulp.lpSum([foods[f][nutrient] * servings[f] for f in foods]) >= min_val, f"Min_{nutrient}"
    prob += pulp.lpSum([foods[f][nutrient] * servings[f] for f in foods]) <= max_val, f"Max_{nutrient}"

# ---------------------------------------------------------
# 4. Solve and Inspect
# ---------------------------------------------------------
prob.solve(pulp.PULP_CBC_CMD(msg=False))
print(f"Solver Status: {pulp.LpStatus[prob.status]}")

if prob.status == pulp.LpStatusOptimal:
    print("\n### Generated Daily Whole-Food Rations ###")
    for food in foods:
        val = servings[food].varValue
        if val and val > 0.05:  # Filter out trivial amounts (<5g)
            grams = round(val * 100, 1)
            print(f"- {food[:50]}: {grams}g")

    print("\n### Daily Totals ###")
    for nutrient in bounds:
        total = sum(
            foods[f][nutrient] * (servings[f].varValue or 0.0)
            for f in foods
        )
        unit = "mg" if nutrient in ["sodium"] else ("kcal" if nutrient == "calories" else "g")
        print(f"{nutrient.capitalize()}: {round(total, 1)} {unit}")
else:
    print("Infeasible: Try relaxing the fiber upper limit or expanding the candidate keyword list.")