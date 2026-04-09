import sqlite3

# 1. Define your nutrients with their standard units
# (g = grams, mg = milligrams, mcg = micrograms)
nutrient_data = [
    ("Water", "g"),
    ("Alpha-linolenic acid", "g"), ("Linoleic acid", "g"),
    ("Histidine", "g"), ("Isoleucine", "g"), ("Leucine", "g"), ("Lysine", "g"), 
    ("Methionine", "g"), ("Phenylalanine", "g"), ("Threonine", "g"), 
    ("Tryptophan", "g"), ("Valine", "g"),
    ("Vitamin A (Retinol)", "mcg"), ("Vitamin C (Ascorbic acid)", "mg"), 
    ("Vitamin D", "mcg"), ("Vitamin E", "mg"), ("Vitamin K", "mcg"), 
    ("Vitamin B1 (Thiamin)", "mg"), ("Vitamin B2 (Riboflavin)", "mg"), 
    ("Vitamin B3 (Niacin)", "mg"), ("Vitamin B5 (Pantothenic acid)", "mg"), 
    ("Vitamin B6 (Pyridoxine)", "mg"), ("Vitamin B7 (Biotin)", "mcg"), 
    ("Vitamin B9 (Folate)", "mcg"), ("Vitamin B12 (Cobalamin)", "mcg"), 
    ("Choline", "mg"),
    ("Calcium", "mg"), ("Chloride", "mg"), ("Magnesium", "mg"), 
    ("Phosphorus", "mg"), ("Potassium", "mg"), ("Sodium", "mg"), ("Sulfur", "mg"),
    ("Chromium", "mcg"), ("Copper", "mg"), ("Fluoride", "mg"), ("Iodine", "mcg"), 
    ("Iron", "mg"), ("Manganese", "mg"), ("Molybdenum", "mcg"), ("Selenium", "mcg"), 
    ("Zinc", "mg")
]

def setup_database(db_name="nutrition.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create Tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS Nutrients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Insert Nutrients (IGNORE skips if they already exist)
    cursor.executemany("""
        INSERT OR IGNORE INTO Nutrients (name, unit) 
        VALUES (?, ?)
    """, nutrient_data)

    conn.commit()
    return conn

def add_ingredient_data(conn, ingredient_name, nutrition_dict):
    """
    Helper function to insert an ingredient and its mapped nutrient amounts.
    nutrition_dict format: {"Water": 86.0, "Vitamin C (Ascorbic acid)": 4.6, ...}
    """
    cursor = conn.cursor()
    
    # 1. Insert the Ingredient
    cursor.execute("INSERT OR IGNORE INTO Ingredients (name) VALUES (?)", (ingredient_name,))
    
    # Get the generated ingredient ID
    cursor.execute("SELECT id FROM Ingredients WHERE name = ?", (ingredient_name,))
    ingredient_id = cursor.fetchone()[0]

    # 2. Insert into the Junction Table
    for nutrient_name, amount in nutrition_dict.items():
        # Get the nutrient ID
        cursor.execute("SELECT id FROM Nutrients WHERE name = ?", (nutrient_name,))
        result = cursor.fetchone()
        
        if result:
            nutrient_id = result[0]
            cursor.execute("""
                INSERT OR REPLACE INTO Ingredient_Nutrients (ingredient_id, nutrient_id, amount)
                VALUES (?, ?, ?)
            """, (ingredient_id, nutrient_id, amount))
        else:
            print(f"Warning: Nutrient '{nutrient_name}' not found in database.")

    conn.commit()

# --- Execution ---
if __name__ == "__main__":
    db_connection = setup_database()
    print("Database and Nutrients created successfully.")

    # Example of adding data (You would loop through your USDA CSV data here)
    sample_apple_data = {
        "Water": 86.2,
        "Vitamin C (Ascorbic acid)": 4.6,
        "Potassium": 107,
        "Calcium": 6
    }
    
    add_ingredient_data(db_connection, "Apple, raw, with skin", sample_apple_data)
    print("Sample ingredient added.")
    
    db_connection.close()