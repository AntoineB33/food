import sqlite3
import sqlite3
import pandas as pd

# 1. Configuration: File paths
DB_PATH = "nutrition.db"
FOOD_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food.csv'
NUTRIENT_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\food_nutrient.csv'
NUTRIENT_DEF_CSV_PATH = r'FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\nutrient.csv'

def setup_database(db_name="nutrition.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create Tables using exact USDA IDs instead of Autoincrement
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Ingredients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS Nutrients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Ingredient_Nutrients (
            ingredient_id INTEGER,
            nutrient_id INTEGER,
            amount REAL NOT NULL,
            PRIMARY KEY (ingredient_id, nutrient_id),
            FOREIGN KEY (ingredient_id) REFERENCES Ingredients(id),
            FOREIGN KEY (nutrient_id) REFERENCES Nutrients(id)
        );
    """)

    conn.commit()
    return conn


def run_bulk_import():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Loading data into memory (this may take a moment)...")
    df_foods = pd.read_csv(FOOD_CSV_PATH)
    df_nutrients = pd.read_csv(NUTRIENT_CSV_PATH)
    df_nutrient_defs = pd.read_csv(NUTRIENT_DEF_CSV_PATH)

    # --- PART 1: IMPORT ALL NUTRIENTS ---
    print(f"Importing {len(df_nutrient_defs)} Nutrients...")
    # Map USDA 'id', 'name', and 'unit_name' directly to our table
    nutrients_to_insert = list(zip(
        df_nutrient_defs['id'], 
        df_nutrient_defs['name'], 
        df_nutrient_defs['unit_name']
    ))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO Nutrients (id, name, unit) 
        VALUES (?, ?, ?)
    """, nutrients_to_insert)
    conn.commit()

    # --- PART 2: IMPORT INGREDIENTS ---
    print(f"Importing {len(df_foods)} Ingredients...")
    foods_to_insert = list(zip(df_foods['fdc_id'], df_foods['description']))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO Ingredients (id, name) 
        VALUES (?, ?)
    """, foods_to_insert)
    conn.commit()

    # --- PART 3: IMPORT JUNCTION DATA ---
    print("Filtering and Importing Nutrition Data...")
    
    # Filter out entries with 0 amount to keep the database lean
    df_filtered_nutrients = df_nutrients[df_nutrients['amount'] > 0]

    # Because our DB uses the exact same IDs as the USDA, no translation dictionary is needed!
    junction_data = list(zip(
        df_filtered_nutrients['fdc_id'],
        df_filtered_nutrients['nutrient_id'],
        df_filtered_nutrients['amount']
    ))

    print(f"Inserting {len(junction_data)} nutrient records...")
    
    cursor.executemany("""
        INSERT OR REPLACE INTO Ingredient_Nutrients (ingredient_id, nutrient_id, amount)
        VALUES (?, ?, ?)
    """, junction_data)

    conn.commit()
    conn.close()
    print("Bulk import completed successfully!")


# --- Execution ---
if __name__ == "__main__":
    db_connection = setup_database()
    print("Database schema created successfully.")
    db_connection.close()
    run_bulk_import()