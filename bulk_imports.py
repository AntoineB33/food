import sqlite3
import pandas as pd

# 1. Configuration: File paths
DB_PATH = "nutrition.db"
FOOD_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food.csv'
NUTRIENT_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food_nutrient.csv'
# Add the path to the nutrient definitions file you just showed me:
NUTRIENT_DEF_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\nutrient.csv'


def run_bulk_import():
    # Connect to your existing database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Loading data into memory (this may take a moment)...")
    
    # Read the USDA CSV files
    df_foods = pd.read_csv(FOOD_CSV_PATH)
    df_nutrients = pd.read_csv(NUTRIENT_CSV_PATH)
    df_nutrient_defs = pd.read_csv(NUTRIENT_DEF_CSV_PATH) # Load the definitions

    print(f"Found {len(df_foods)} foods in the USDA dataset.")

    # --- NEW: AUTOMATICALLY GENERATE THE DICTIONARY ---
    print("Generating USDA ID mapping...")
    # This turns the two columns ('id' and 'name') into a Python dictionary: {2047: "Energy...", 1003: "Protein", ...}
    USDA_ID_TO_LOCAL_NAME = pd.Series(df_nutrient_defs['name'].values, index=df_nutrient_defs['id']).to_dict()

    # --- PART 1: IMPORT INGREDIENTS ---
    print("Importing Ingredients...")
    foods_to_insert = list(zip(df_foods['fdc_id'], df_foods['description']))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO Ingredients (id, name) 
        VALUES (?, ?)
    """, foods_to_insert)
    conn.commit()


    # --- PART 2: GET LOCAL NUTRIENT IDs ---
    cursor.execute("SELECT id, name FROM Nutrients")
    local_nutrients = {name: id for id, name in cursor.fetchall()}

    
    # --- PART 3: FILTER AND IMPORT JUNCTION DATA ---
    print("Filtering and Importing Nutrition Data...")
    
    # Filter the massive USDA dataset to ONLY include the nutrient IDs we have mapped
    valid_usda_ids = list(USDA_ID_TO_LOCAL_NAME.keys())
    df_filtered_nutrients = df_nutrients[df_nutrients['nutrient_id'].isin(valid_usda_ids)]

    # Prepare data for the junction table
    junction_data = []
    
    for index, row in df_filtered_nutrients.iterrows():
        food_id = row['fdc_id']
        usda_nut_id = row['nutrient_id']
        amount = row['amount']
        
        # Translate USDA ID -> Your String Name -> Your Database ID
        local_name = USDA_ID_TO_LOCAL_NAME.get(usda_nut_id)
        local_db_id = local_nutrients.get(local_name)

        # Because we mapped ALL USDA nutrients, 'local_db_id' will be None for anything 
        # that isn't one of your 42 specific nutrients. The 'if' statement cleanly skips them!
        if local_db_id and amount > 0:
            junction_data.append((food_id, local_db_id, amount))

    print(f"Inserting {len(junction_data)} nutrient records...")
    
    cursor.executemany("""
        INSERT OR REPLACE INTO Ingredient_Nutrients (ingredient_id, nutrient_id, amount)
        VALUES (?, ?, ?)
    """, junction_data)

    conn.commit()
    conn.close()
    print("Bulk import completed successfully!")

if __name__ == "__main__":
    run_bulk_import()