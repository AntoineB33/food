import sqlite3
import pandas as pd

# Import your mappings and DB path from your existing files
from essential_nutrients import daily_nutrient_intervals, usda_nutrient_mapping
from ingredients_nutrients_db_generator import DB_PATH

def count_complete_recipes(db_path):
    # 1. Connect and fetch data from the Recipe_Nutrients view
    conn = sqlite3.connect(db_path)
    # We only need the recipe name and nutrient name for this check
    query = """
    SELECT recipe_name, nutrient_name 
    FROM Recipe_Nutrients
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Map USDA DB names back to your Essential Nutrient keys
    reverse_mapping = {v: k for k, v in usda_nutrient_mapping.items()}
    df['essential_nutrient'] = df['nutrient_name'].map(reverse_mapping)
    
    # Drop rows that aren't in your essential nutrients list
    df = df.dropna(subset=['essential_nutrient'])

    # 3. Determine the actual required nutrients
    # What we want: all nutrients in your intervals
    desired_nutrients = set(daily_nutrient_intervals.keys())
    
    # What we have: essential nutrients that actually appear in the database at least once
    present_nutrients = set(df['essential_nutrient'].unique())
    
    # "Except the ones that nobody has" -> Intersection of desired and present
    actually_required_nutrients = desired_nutrients.intersection(present_nutrients)
    target_count = len(actually_required_nutrients)

    print(f"Total essential nutrients defined: {len(desired_nutrients)}")
    print(f"Essential nutrients found in DB: {target_count}")
    
    if target_count < len(desired_nutrients):
        missing = desired_nutrients - present_nutrients
        print(f"Ignoring missing nutrients: {', '.join(missing)}\n")

    # 4. Count unique nutrients per recipe
    # Group by recipe_name and count how many unique essential nutrients it has
    nutrient_counts_per_recipe = df.groupby('recipe_name')['essential_nutrient'].nunique()

    # 5. Filter and count recipes that have ALL the actually required nutrients
    complete_recipes = nutrient_counts_per_recipe[nutrient_counts_per_recipe == target_count]
    
    number_of_complete_recipes = len(complete_recipes)
    
    print("-" * 50)
    print(f"Number of recipes with complete nutrient data: {number_of_complete_recipes}")
    print("-" * 50)
    
    return number_of_complete_recipes

if __name__ == "__main__":
    count_complete_recipes(DB_PATH)