import pandas as pd
import sqlite3
import ast
from thefuzz import process, fuzz
import re

# ==========================================
# 1. ACTUAL FILE PATHS
# ==========================================
# USDA Foundation Foods Files
USDA_FOOD_FILE = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food.csv'
USDA_NUTRIENT_FILE = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\nutrient.csv'
USDA_FOOD_NUTRIENT_FILE = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food_nutrient.csv'

# Kaggle Recipe Files
KAGGLE_RECIPES_FILE = r'archive\RAW_recipes.csv'

LOCAL_DB_NAME = 'massive_nutrition_recipes.db'

def clean_recipe_ingredient(ingredient_string):
    """Strips measurements and prep words for better NLP matching."""
    stop_words = ['cups', 'cup', 'tbsp', 'tsp', 'ounces', 'oz', 'grams', 'g', 'lbs', 
                  'chopped', 'diced', 'minced', 'sliced', 'peeled', 'fresh', 'large', 'small']
    clean_str = re.sub(r'[^a-zA-Z\s]', '', ingredient_string).lower()
    words = clean_str.split()
    return " ".join([word for word in words if word not in stop_words])

def build_usda_master_table():
    """Merges the scattered USDA tables into one master flat DataFrame."""
    print("Stitching USDA relational tables together...")
    
    food_df = pd.read_csv(USDA_FOOD_FILE, usecols=['fdc_id', 'description'])
    nutrient_df = pd.read_csv(USDA_NUTRIENT_FILE, usecols=['id', 'name', 'unit_name'])
    food_nutr_df = pd.read_csv(USDA_FOOD_NUTRIENT_FILE, usecols=['fdc_id', 'nutrient_id', 'amount'])
    
    # 1. Merge the nutrient names onto the amounts
    merged_nutrients = pd.merge(food_nutr_df, nutrient_df, left_on='nutrient_id', right_on='id')
    
    # 2. Pivot the table so each nutrient becomes its own column (Zinc, Mag, Vit D, etc.)
    # This transforms millions of rows into a clean, wide database
    print("Pivoting micronutrients (this takes a moment)...")
    pivot_df = merged_nutrients.pivot_table(index='fdc_id', columns='name', values='amount', aggfunc='first').reset_index()
    
    # 3. Merge the food descriptions back onto the pivoted nutrients
    usda_master = pd.merge(food_df, pivot_df, on='fdc_id')
    
    return usda_master

def build_database():
    # 1. Build the master USDA table
    usda_df = build_usda_master_table()
    
    # 2. Load the Kaggle Recipes
    print(f"Loading {KAGGLE_RECIPES_FILE}...")
    # RAW_recipes.csv usually has columns: name, id, minutes, contributor_id, submitted, tags, nutrition, n_steps, steps, description, ingredients, n_ingredients
    recipes_df = pd.read_csv(KAGGLE_RECIPES_FILE, usecols=['id', 'name', 'ingredients'])
    
    print("Establishing SQLite Database...")
    conn = sqlite3.connect(LOCAL_DB_NAME)
    
    # Save the flattened USDA table
    print("Saving USDA Master Table to SQLite...")
    usda_df.to_sql('raw_ingredients', conn, if_exists='replace', index=False)
    
    usda_ingredient_names = usda_df['description'].dropna().tolist()
    recipe_ingredient_mappings = []

    print("Mapping Recipe Ingredients to USDA Database...")
    print("WARNING: Fuzzy matching hundreds of thousands of recipes will take significant time.")
    
    # For testing, we are only processing the first 100 recipes. 
    # Remove the .head(100) when you are ready to process all 294MB.
    for index, row in recipes_df.head(100).iterrows():
        try:
            # Kaggle saves lists as string literals: "['chicken', 'salt']"
            raw_ingredients = ast.literal_eval(row['ingredients'])
        except (ValueError, SyntaxError):
            continue # Skip malformed rows
            
        for raw_ing in raw_ingredients:
            cleaned_ing = clean_recipe_ingredient(raw_ing)
            
            # Fuzzy Match
            best_match = process.extractOne(cleaned_ing, usda_ingredient_names, scorer=fuzz.token_set_ratio, score_cutoff=75)
            matched_usda_name = best_match[0] if best_match else "Unmatched"
            
            recipe_ingredient_mappings.append({
                'recipe_id': row['id'],
                'recipe_title': row['name'],
                'original_recipe_ingredient': raw_ing,
                'matched_usda_ingredient': matched_usda_name
            })

    # Save mapping table
    mapping_df = pd.DataFrame(recipe_ingredient_mappings)
    mapping_df.to_sql('recipe_ingredients', conn, if_exists='replace', index=False)
    
    print(f"\nSuccess! Local database '{LOCAL_DB_NAME}' generated.")
    conn.close()

if __name__ == "__main__":
    build_database()