import sqlite3
import pandas as pd

# 1. Configuration: File paths
DB_PATH = "nutrition.db"
FOOD_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food.csv'
NUTRIENT_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food_nutrient.csv'

# 2. Map USDA Nutrient IDs to YOUR database's exact nutrient names.
# You will need to look at the USDA's 'nutrient.csv' to find the IDs for all 42 of your nutrients.
# Here is a sample of what that mapping looks like:
USDA_ID_TO_LOCAL_NAME = {
    1051: "Water",
    1162: "Vitamin C (Ascorbic acid)",
    1092: "Potassium",
    1087: "Calcium",
    1089: "Iron",
    1090: "Magnesium",
    1091: "Phosphorus",
    1093: "Sodium",
    1095: "Zinc"
    # ... add the rest of your 42 nutrients here ...
}

def run_bulk_import():
    # Connect to your existing database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Loading data into memory (this may take a moment)...")
    
    # Read the USDA CSV files
    df_foods = pd.read_csv(FOOD_CSV_PATH)
    df_nutrients = pd.read_csv(NUTRIENT_CSV_PATH)

    print(f"Found {len(df_foods)} foods in the USDA dataset.")

    # --- PART 1: IMPORT INGREDIENTS ---
    print("Importing Ingredients...")
    # Prepare a list of tuples: (fdc_id, description)
    # We will temporarily insert the USDA's 'fdc_id' into our DB as the Primary Key 
    # to make linking the junction table much easier.
    
    # NOTE: If your Ingredients table doesn't have an 'id' that you can manually set, 
    # SQLite allows you to insert into the AUTOINCREMENT column if you specify it.
    foods_to_insert = list(zip(df_foods['fdc_id'], df_foods['description']))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO Ingredients (id, name) 
        VALUES (?, ?)
    """, foods_to_insert)
    conn.commit()


    # --- PART 2: GET LOCAL NUTRIENT IDs ---
    # We need to know the ID of "Water" or "Calcium" inside YOUR database.
    cursor.execute("SELECT id, name FROM Nutrients")
    local_nutrients = {name: id for id, name in cursor.fetchall()}

    
    # --- PART 3: FILTER AND IMPORT JUNCTION DATA ---
    print("Filtering and Importing Nutrition Data...")
    
    # Filter the massive USDA dataset to ONLY include the nutrient IDs in your dictionary
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

        # Only add if the amount is greater than 0 to save space, and if the nutrient exists in your DB
        if local_db_id and amount > 0:
            junction_data.append((food_id, local_db_id, amount))

    print(f"Inserting {len(junction_data)} nutrient records...")
    
    # Use executemany for massive performance gains (inserts thousands of rows per second)
    cursor.executemany("""
        INSERT OR REPLACE INTO Ingredient_Nutrients (ingredient_id, nutrient_id, amount)
        VALUES (?, ?, ?)
    """, junction_data)

    conn.commit()
    conn.close()
    print("Bulk import completed successfully!")

if __name__ == "__main__":
    run_bulk_import()