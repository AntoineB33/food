import sqlite3
import pandas as pd
import pulp

# Import your mappings and intervals from the local file
from essential_nutrients import daily_nutrient_intervals, usda_nutrient_mapping

def solve_daily_menu(db_path="nutrition.db"):
    # 1. Connect to Database and Extract Data
    conn = sqlite3.connect(db_path)
    
    # Assuming standard column names for the junction table: ingredient_id, nutrient_id, amount
    query = """
    SELECT 
        i.name as ingredient_name, 
        n.name as nutrient_name, 
        inu.amount
    FROM Ingredients i
    JOIN Ingredient_Nutrients inu ON i.ID = inu.ingredient_id
    JOIN Nutrients n ON n.ID = inu.nutrient_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Map USDA DB names to your Essential Nutrient keys
    # Create a reverse dictionary of usda_nutrient_mapping
    reverse_mapping = {v: k for k, v in usda_nutrient_mapping.items()}
    
    # Filter only for essential nutrients and rename them to match your intervals
    df['essential_nutrient'] = df['nutrient_name'].map(reverse_mapping)
    df = df.dropna(subset=['essential_nutrient'])

    # 3. Create a Nutrient Matrix (Rows: Ingredients, Cols: Nutrients)
    # If there are duplicate entries for the same ingredient/nutrient combo, we take the mean
    matrix = df.pivot_table(
        index='ingredient_name', 
        columns='essential_nutrient', 
        values='amount',
        aggfunc='mean'
    ).fillna(0)

    # 4. Initialize the Linear Programming Problem
    # We want to minimize the total amount of food consumed
    prob = pulp.LpProblem("Optimal_Daily_Menu", pulp.LpMinimize)

    # Create a continuous variable for each ingredient (amount >= 0)
    food_vars = pulp.LpVariable.dicts("Food", matrix.index, lowBound=0, cat='Continuous')

    # Objective Function: Minimize the sum of all food variables
    prob += pulp.lpSum([food_vars[f] for f in matrix.index]), "Total_Food_Amount"

    # 5. Add Constraints for each nutrient based on your daily_nutrient_intervals
    for nutrient, (min_val, max_val) in daily_nutrient_intervals.items():
        if nutrient in matrix.columns:
            # Nutrient total calculation: sum of (amount in food * food_variable)
            nutrient_total = pulp.lpSum([matrix.loc[f, nutrient] * food_vars[f] for f in matrix.index])
            
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
        print("Optimal Daily Menu (Multipliers of base DB unit, typically 100g):")
        print("-" * 50)
        
        total_weight_multiplier = 0
        for f in matrix.index:
            amount = food_vars[f].varValue
            if amount is not None and amount > 0.01: # Filter out trace zero amounts
                print(f"{f}: {amount:.2f} units")
                total_weight_multiplier += amount
                
        print("-" * 50)
        print(f"Total Base Units Consumed: {total_weight_multiplier:.2f}")
    else:
        print("No feasible menu could be found. The constraints may be too tight, or the database lacks foods to fulfill specific nutrient combinations.")

if __name__ == "__main__":
    solve_daily_menu("nutrition.db")