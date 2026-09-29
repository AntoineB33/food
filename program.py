import pandas as pd
import pulp

# 1. Load the Nutritional Database from the CSV file
df = pd.read_csv("vegan_database.csv")

# Convert the pandas dataframe into a dictionary formatted for the PuLP solver
# This automatically maps the 'Food_Name' column to the dictionary keys
foods = df.set_index('Food_Name').to_dict(orient='index')

# Now the 'foods' dictionary is identical in structure to the previous manual one,
# and you can run the rest of the PuLP solver code exactly as before!

# 2. Define the Minimum and Maximum Bounds (from your table)
# We will use Leucine in grams (3.0g to 6.0g) to keep units manageable.
bounds = {
    "calories": (2350, 2550),
    "protein": (150, 180),
    "fat": (65, 85),
    "carbs": (240, 310),
    "fiber": (34, 65),     # Crucial constraint to prevent extreme fiber loads
    "sodium": (1500, 3000),
    "leucine": (3.0, 6.0)
}

# 3. Initialize the Mixed-Integer Linear Programming (MILP) Problem
# We use LpMinimize, aiming to minimize total calories to stay lean, 
# while strictly obeying all minimum bounds.
prob = pulp.LpProblem("Vegan_Recomposition_Diet", pulp.LpMinimize)

# 4. Create Decision Variables (How many servings of each food?)
# 'lowBound=0' prevents negative servings.
# 'cat="Integer"' forces whole servings (1, 2, 3) instead of fractions.
# 'upBound=3' prevents the solver from just feeding you 8 bowls of oatmeal.
servings = {
    food: pulp.LpVariable(f"servings_{str(food).replace(' ', '_')}", lowBound=0, upBound=3, cat="Integer") 
    for food in foods
}

# 5. Set the Objective Function: Minimize Total Calories
prob += pulp.lpSum([foods[food]["calories"] * servings[food] for food in foods]), "Total_Calories"

# 6. Apply the Constraints programmatically
for nutrient, (min_val, max_val) in bounds.items():
    # Sum of (Nutrient per serving * Number of servings) >= Min Target
    prob += pulp.lpSum([foods[food][nutrient] * servings[food] for food in foods]) >= min_val, f"Min_{nutrient}"
    # Sum of (Nutrient per serving * Number of servings) <= Max Target
    prob += pulp.lpSum([foods[food][nutrient] * servings[food] for food in foods]) <= max_val, f"Max_{nutrient}"

# 7. Add a "Variety Constraint" (Optional but recommended)
# Force the solver to include at least 3 total servings of "base" meals, rather than just surviving on protein powder and rice.
base_meals = [food for food, data in foods.items() if data["type"] == "base"]
prob += pulp.lpSum([servings[food] for food in base_meals]) >= 3, "Minimum_Base_Meals"

# 8. Solve the Problem
prob.solve()

# 9. Output the Results
print(f"Status: {pulp.LpStatus[prob.status]}\n")

if prob.status == pulp.LpStatusOptimal:
    print("### Optimal Daily Meal Plan ###")
    for food in foods:
        qty = servings[food].varValue
        if qty is not None and qty > 0:
            print(f"- {int(qty)}x {food}")

    print("\n### Daily Totals Achieved ###")
    for nutrient in bounds:
        total = sum([foods[food][nutrient] * servings[food].varValue for food in foods])
        print(f"{nutrient.capitalize()}: {round(total, 1)}")
else:
    print("No feasible combination found. Adjust your bounds or add more diverse foods to the database.")