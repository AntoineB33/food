import numpy as np
from scipy.optimize import minimize
import itertools

# --- 1. Mock Database ---
# Representing the tables as dictionaries for demonstration

nutrients = {
    1: {"name": "Vitamin C", "unit": "mg"},
    2: {"name": "Protein", "unit": "grams"}
}

recipes = {
    101: {
        "name": "Customizable Oatmeal",
        "num_ingredients": 2, # e.g., Oats, Milk
        # Variation constraint: ingredient 0 must be > 0.5 * ingredient 1
        "compounds_variations_string": "q[0] - 0.5 * q[1]", 
        # Returns a dict of nutrient outputs based on time (t) and quantities (q)
        "formula_string": "{1: q[0]*0.1 + q[1]*1.2 + t*0, 2: q[0]*0.15 + q[1]*3.0}"
    },
    102: {
        "name": "Fruit Salad",
        "num_ingredients": 2, # e.g., Apples, Oranges
        "compounds_variations_string": "q[0] + q[1] - 100", # minimum 100g total
        "formula_string": "{1: q[0]*5.0 + q[1]*50.0, 2: q[0]*0.2 + q[1]*0.9}"
    }
}

meals = {
    201: {"nutrient_id": 1, "min": 10, "max": 500}, # Breakfast
    202: {"nutrient_id": 2, "min": 20, "max": 100}  # Lunch
}

days_meals = {1: [201, 202]} # Day 1 consists of Breakfast and Lunch

days_needs = {
    1: {"daily_min": 50, "daily_max": 1000}, # Vitamin C daily bounds
    2: {"daily_min": 50, "daily_max": 200}   # Protein daily bounds
}

# --- 2. Helper Functions for String Evaluation ---

def eval_variation(string_formula, q):
    """Evaluates the internal recipe ingredient constraints."""
    return eval(string_formula, {"q": q, "np": np})

def eval_nutrients(string_formula, t, q):
    """Evaluates the nutrient output for a recipe."""
    return eval(string_formula, {"t": t, "q": q, "np": np})

# --- 3. The Optimization Engine ---

def solve_daily_plan(day_id):
    meal_ids = days_meals[day_id]
    num_meals = len(meal_ids)
    
    # Generate all possible recipe combinations for the day's meals
    recipe_options = list(recipes.keys())
    recipe_combinations = list(itertools.product(recipe_options, repeat=num_meals))
    
    # We will just try to find a *feasible* solution (objective = 0)
    def objective(x):
        return 0.0

    for combo in recipe_combinations:
        # x is a flat array containing [t1, q1_1, q1_2, ..., t2, q2_1, q2_2...]
        # First, calculate how many variables we need
        var_counts = [1 + recipes[r]["num_ingredients"] for r in combo]
        total_vars = sum(var_counts)
        
        # Initial guess: Time = 10, Quantities = 50
        x0 = np.full(total_vars, 50.0)
        for i in range(len(combo)):
            idx = sum(var_counts[:i])
            x0[idx] = 10.0 # Initial guess for time
            
        constraints = []
        
        # Build constraints dynamically based on the current recipe combination
        def make_recipe_variation_constraint(r_id, start_idx):
            return lambda x: eval_variation(recipes[r_id]["compounds_variations_string"], 
                                            x[start_idx+1 : start_idx + 1 + recipes[r_id]["num_ingredients"]])

        # 1. Add Recipe internal constraints
        for i, r_id in enumerate(combo):
            start_idx = sum(var_counts[:i])
            constraints.append({
                'type': 'ineq', # ineq means function must be >= 0 in scipy
                'fun': make_recipe_variation_constraint(r_id, start_idx)
            })
            
        # 2. Add Meal-specific nutrient constraints
        def make_meal_constraint(meal_id, r_id, start_idx, is_min):
            def constraint_func(x):
                t = x[start_idx]
                q = x[start_idx+1 : start_idx + 1 + recipes[r_id]["num_ingredients"]]
                nutrients_out = eval_nutrients(recipes[r_id]["formula_string"], t, q)
                nut_id = meals[meal_id]["nutrient_id"]
                val = nutrients_out.get(nut_id, 0)
                
                if is_min:
                    return val - meals[meal_id]["min"] # val >= min  =>  val - min >= 0
                else:
                    return meals[meal_id]["max"] - val # val <= max  =>  max - val >= 0
            return constraint_func

        for i, meal_id in enumerate(meal_ids):
            r_id = combo[i]
            start_idx = sum(var_counts[:i])
            constraints.append({'type': 'ineq', 'fun': make_meal_constraint(meal_id, r_id, start_idx, is_min=True)})
            constraints.append({'type': 'ineq', 'fun': make_meal_constraint(meal_id, r_id, start_idx, is_min=False)})

        # 3. Add Daily total nutrient constraints
        def make_daily_constraint(nut_id, is_min):
            def constraint_func(x):
                total_nutrient = 0
                for i, r_id in enumerate(combo):
                    start_idx = sum(var_counts[:i])
                    t = x[start_idx]
                    q = x[start_idx+1 : start_idx + 1 + recipes[r_id]["num_ingredients"]]
                    nutrients_out = eval_nutrients(recipes[r_id]["formula_string"], t, q)
                    total_nutrient += nutrients_out.get(nut_id, 0)
                
                if is_min:
                    return total_nutrient - days_needs[nut_id]["daily_min"]
                else:
                    return days_needs[nut_id]["daily_max"] - total_nutrient
            return constraint_func

        for nut_id in days_needs.keys():
            constraints.append({'type': 'ineq', 'fun': make_daily_constraint(nut_id, is_min=True)})
            constraints.append({'type': 'ineq', 'fun': make_daily_constraint(nut_id, is_min=False)})

        # Add bounds so quantities and times are always positive
        bounds = [(0, None) for _ in range(total_vars)]

        # Run the solver
        result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)
        
        if result.success:
            print("Found a valid food plan!")
            print(f"Recipes to cook: {[recipes[r]['name'] for r in combo]}")
            
            for i, r_id in enumerate(combo):
                start_idx = sum(var_counts[:i])
                t = result.x[start_idx]
                q = result.x[start_idx+1 : start_idx + 1 + recipes[r_id]["num_ingredients"]]
                print(f"  Meal {meal_ids[i]} ({recipes[r_id]['name']}): Time = {t:.2f}, Ingredients = {np.round(q, 2)}")
            return result

    print("No feasible food plan found for any recipe combination.")
    return None

# Execute
solve_daily_plan(day_id=1)