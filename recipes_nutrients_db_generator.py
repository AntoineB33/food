import sqlite3

from ingredients_nutrients_db_generator import DB_PATH

def expand_database_with_recipes(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    print("Creating Recipe tables and views...")

    cursor.executescript("""
        -- 1. Create Recipes Table
        CREATE TABLE IF NOT EXISTS Recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            instructions TEXT
        );

        -- 2. Create Junction Table: Recipes -> Ingredients
        -- amount_grams is critical because USDA data is per 100g
        CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
            recipe_id INTEGER,
            ingredient_id INTEGER,
            amount_grams REAL NOT NULL,
            PRIMARY KEY (recipe_id, ingredient_id),
            FOREIGN KEY (recipe_id) REFERENCES Recipes(id),
            FOREIGN KEY (ingredient_id) REFERENCES Ingredients(id)
        );

        -- 3. Create a VIEW for Recipe Nutrients
        -- This dynamically calculates total recipe nutrients based on ingredient amounts.
        -- Formula: (USDA nutrient amount / 100) * ingredient grams in recipe
        CREATE VIEW IF NOT EXISTS Recipe_Nutrients AS
        SELECT 
            ri.recipe_id,
            r.name AS recipe_name,
            n.id AS nutrient_id,
            n.name AS nutrient_name,
            SUM(inx.amount * (ri.amount_grams / 100.0)) AS total_amount,
            n.unit
        FROM Recipe_Ingredients ri
        JOIN Recipes r ON ri.recipe_id = r.id
        JOIN Ingredient_Nutrients inx ON ri.ingredient_id = inx.ingredient_id
        JOIN Nutrients n ON inx.nutrient_id = n.id
        GROUP BY ri.recipe_id, n.id;
    """)

    conn.commit()
    print("Recipe schema added successfully!")
    return conn

def insert_test_recipe(conn):
    cursor = conn.cursor()
    
    # Example: Let's assume we looked up the USDA IDs for these items.
    # 170456 = "Milk, whole, 3.25% milkfat, with added vitamin D"
    # 173436 = "Butter, without salt"
    
    # 1. Insert a mock recipe
    cursor.execute("INSERT OR IGNORE INTO Recipes (id, name, instructions) VALUES (?, ?, ?)", 
                   (1, "Buttered Milk", "Melt butter. Pour into milk. Regret choices."))
    
    # 2. Add ingredients to the recipe (e.g., 250g milk, 15g butter)
    cursor.executemany("""
        INSERT OR IGNORE INTO Recipe_Ingredients (recipe_id, ingredient_id, amount_grams)
        VALUES (?, ?, ?)
    """, [
        (1, 170456, 250.0), 
        (1, 173436, 15.0)    
    ])
    conn.commit()
    
    # 3. Query the VIEW to see the magic happen
    print("\n--- Nutritional Profile for 'Buttered Milk' ---")
    
    # Fetching Energy (kcal) and Protein as a test
    cursor.execute("""
        SELECT nutrient_name, ROUND(total_amount, 2), unit 
        FROM Recipe_Nutrients 
        WHERE recipe_id = 1 AND nutrient_name IN ('Energy', 'Protein')
    """)
    
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]} {row[2]}")

if __name__ == "__main__":
    db_conn = expand_database_with_recipes(DB_PATH)
    
    # Optional: Run the test to see how the VIEW calculates the data
    # NOTE: This will only yield results if IDs 170456 and 173436 exist in your downloaded USDA dataset!
    try:
        insert_test_recipe(db_conn)
    except Exception as e:
        print(f"Could not run test insertion (perhaps specific USDA IDs are missing from your subset): {e}")
        
    db_conn.close()