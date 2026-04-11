import sqlite3
import pandas as pd
import pulp

# Import your mappings and intervals from the local file
from essential_nutrients import daily_nutrient_intervals, usda_nutrient_mapping
from ingredients_nutrients_db_generator import DB_PATH

def solve_daily_menu_with_recipes(db_path):
    # 1. Connect to Database and Extract Data
    conn = sqlite3.connect(db_path)
    
    # Query the Recipe_Nutrients view. 
    # Because this view already aggregates nutrients per whole recipe,
    # 'amount' here represents the total nutrient yield of 1 recipe.
    query = """
    SELECT 
        recipe_name, 
        nutrient_name, 
        total_amount as amount
    FROM Recipe_Nutrients
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Map USDA DB names to your Essential Nutrient keys
    # Create a reverse dictionary of usda_nutrient_mapping
    reverse_mapping = {v: k for k, v in usda_nutrient_mapping.items()}
    
    # Filter only for essential nutrients and rename them to match your intervals
    df['essential_nutrient'] = df['nutrient_name'].map(reverse_mapping)
    df = df.dropna(subset=['essential_nutrient'])

    # 3. Create a Nutrient Matrix (Rows: Recipes, Cols: Nutrients)
    matrix = df.pivot_table(
        index='recipe_name', 
        columns='essential_nutrient', 
        values='amount',
        aggfunc='mean'
    ).fillna(0)

    # 4. Initialize the Linear Programming Problem
    # We want to minimize the total quantity of recipes consumed
    prob = pulp.LpProblem("Optimal_Daily_Recipe_Menu", pulp.LpMinimize)

    # Create a continuous variable for each recipe (amount >= 0)
    # 1 unit = 1 complete recipe
    recipe_vars = pulp.LpVariable.dicts("Recipe", matrix.index, lowBound=0, cat='Continuous')

    # Objective Function: Minimize the sum of all recipe variables
    prob += pulp.lpSum([recipe_vars[r] for r in matrix.index]), "Total_Recipe_Amount"

    # 5. Add Constraints for each nutrient based on your daily_nutrient_intervals
    for nutrient, (min_val, max_val) in daily_nutrient_intervals.items():
        if nutrient in matrix.columns:
            # Nutrient total calculation: sum of (total amount in recipe * recipe_variable)
            nutrient_total = pulp.lpSum([matrix.loc[r, nutrient] * recipe_vars[r] for r in matrix.index])
            
            # Add Min and Max constraints
            prob += nutrient_total >= min_val, f"Min_{nutrient.replace(' ', '_')}"
            prob += nutrient_total <= max_val, f"Max_{nutrient.replace(' ', '_')}"
        else:
            print(f"Warning: '{nutrient}' has no data in the database. Constraints skipped.")

    # 6. Solve the Equation
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # 7. Evaluate and Print Results
    status = pulp.LpStatus[prob.status]
    print(f"Solver Status: {status}\n")

    if status == "Optimal":
        print("Optimal Daily Menu (in fractions of whole recipes):")
        print("-" * 60)
        
        total_recipes_multiplier = 0
        for r in matrix.index:
            amount = recipe_vars[r].varValue
            if amount is not None and amount > 0.001: # Filter out trace zero amounts
                # Amount is printed as a multiplier/fraction of the full recipe
                print(f"{r}: {amount:.3f}x of the recipe")
                total_recipes_multiplier += amount
                
        print("-" * 60)
        print(f"Total Combined Recipes Consumed: {total_recipes_multiplier:.3f}")
    else:
        print("No feasible menu could be found. The constraints may be too tight, or the database lacks recipes to fulfill specific nutrient combinations.")

if __name__ == "__main__":
    solve_daily_menu_with_recipes(DB_PATH)