import sqlite3
import pandas as pd
import pulp

# ==========================================
# 1. NUTRITIONAL TARGETS (From your specs)
# ==========================================
TARGETS = {
    'Calories': {'min': 2200, 'target': 2250, 'max': 2300},
    'Protein': {'min': 150, 'max': 160},
    'Carbs': {'min': 250, 'max': 260},
    'Fat': {'min': 65, 'max': 70},
    'Fiber': {'min': 32, 'max': 50}, # No real upper limit needed, but keeps solver grounded
    'Sodium': {'min': 2000, 'max': 2500},
    'Potassium': {'min': 3400, 'max': 4700},
    'Magnesium': {'min': 400, 'max': 450},
    'Zinc': {'min': 11, 'max': 15},
    'Vitamin_C': {'min': 90, 'max': 2000}
}

LOCAL_DB_NAME = 'massive_nutrition_recipes.db'

def load_recipe_data():
    """
    Loads the aggregated nutritional data for each recipe.
    Note: You must create this table/view in your DB by multiplying 
    your matched USDA ingredients by their actual recipe quantities!
    """
    conn = sqlite3.connect(LOCAL_DB_NAME)
    
    # Mocking the query. In reality, you'd select from your aggregated table.
    # Columns expected: recipe_id, recipe_title, Calories, Protein, Carbs, Fat, etc.
    query = """
        SELECT 
            recipe_id, recipe_title, 
            Calories, Protein, Carbs, Fat, Fiber, 
            Sodium, Potassium, Magnesium, Zinc, Vitamin_C
        FROM recipe_nutritional_totals
    """
    
    try:
        df = pd.read_sql(query, conn)
    except sqlite3.OperationalError:
        print("Error: 'recipe_nutritional_totals' table not found.")
        print("Please ensure you have calculated the total macros per recipe first.")
        conn.close()
        return None
        
    conn.close()
    return df

def generate_meal_plan(recipes_df):
    """Solves the MILP equation to find the perfect daily recipe combination."""
    print("\nInitializing Optimization Solver...")
    
    # 1. Define the Problem: We want to MINIMIZE caloric deviation from target
    prob = pulp.LpProblem("Daily_Meal_Plan_Optimizer", pulp.LpMinimize)
    
    # 2. Define the Decision Variables: Which recipes do we eat?
    # Cat = 'Integer' means we can't eat 0.45 of a recipe. 
    # LowBound = 0 means no negative eating. UpBound = 2 means max 2 servings of the same thing.
    recipe_vars = pulp.LpVariable.dicts(
        "Recipe", 
        recipes_df['recipe_id'].tolist(), 
        lowBound=0, 
        upBound=2, 
        cat='Integer'
    )
    
    # 3. Add Constraints (The bounds you set for your 24yo athletic profile)
    # Total Meals Limit (e.g., eat 3 to 5 distinct meals/snacks a day)
    prob += pulp.lpSum([recipe_vars[r] for r in recipes_df['recipe_id']]) >= 3, "Min_Meals"
    prob += pulp.lpSum([recipe_vars[r] for r in recipes_df['recipe_id']]) <= 5, "Max_Meals"
    
    # Macro & Micro Constraints
    for nutrient, limits in TARGETS.items():
        if 'min' in limits:
            prob += pulp.lpSum([recipes_df[recipes_df['recipe_id'] == r][nutrient].values[0] * recipe_vars[r] 
                                for r in recipes_df['recipe_id']]) >= limits['min'], f"Min_{nutrient}"
        if 'max' in limits:
            prob += pulp.lpSum([recipes_df[recipes_df['recipe_id'] == r][nutrient].values[0] * recipe_vars[r] 
                                for r in recipes_df['recipe_id']]) <= limits['max'], f"Max_{nutrient}"

    # 4. Define the Objective Function (Minimize the difference from 2250 Calories)
    # To do this linearly, we minimize the total calories since our hard bounds (2200-2300) 
    # already force it to be accurate.
    prob += pulp.lpSum([recipes_df[recipes_df['recipe_id'] == r]['Calories'].values[0] * recipe_vars[r] 
                        for r in recipes_df['recipe_id']]), "Total_Calories"

    # 5. Solve the Equation
    prob.solve()

    # 6. Output the Results
    if pulp.LpStatus[prob.status] != "Optimal":
        print(f"Solver Status: {pulp.LpStatus[prob.status]}")
        print("Could not find a combination of recipes that perfectly matches your strict criteria.")
        print("Try widening your macro/micro bounds slightly.")
        return

    print("\n==========================================")
    print("🎯 OPTIMAL MEAL PLAN FOUND")
    print("==========================================")
    
    total_macros = {k: 0 for k in TARGETS.keys()}
    
    for v in prob.variables():
        if v.varValue is not None and v.varValue > 0:
            # Extract recipe ID from variable name (e.g., "Recipe_12345")
            r_id = int(v.name.split('_')[1])
            recipe_row = recipes_df[recipes_df['recipe_id'] == r_id].iloc[0]
            
            servings = int(v.varValue)
            print(f"[{servings}x] {recipe_row['recipe_title']}")
            
            # Tally up the final macros
            for nutrient in TARGETS.keys():
                total_macros[nutrient] += recipe_row[nutrient] * servings

    print("\n📊 YOUR DAILY NUTRITION TOTALS:")
    for nutrient, total in total_macros.items():
        unit = "kcal" if nutrient == 'Calories' else "mg" if nutrient in ['Sodium', 'Potassium', 'Magnesium', 'Zinc', 'Vitamin_C'] else "g"
        print(f"- {nutrient}: {total:.1f} {unit} (Target: {TARGETS[nutrient].get('min', 0)}-{TARGETS[nutrient].get('max', '+')} {unit})")


if __name__ == "__main__":
    df = load_recipe_data()
    if df is not None:
        generate_meal_plan(df)