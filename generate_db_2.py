import sqlite3

# Configuration: File path for the empty database
DB_PATH = "recipe_nutrition_2.db"

def create_schema(db_name):
    """
    Connects to the specified database and generates the complete schema 
    for ingredients, nutrients, and recipes without inserting any data.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    print("Generating database schema...")

    cursor.executescript("""
        -- ==========================================
        -- 1. Foundation Tables (USDA Data Structure)
        -- ==========================================

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

        -- ==========================================
        -- 2. Recipe Application Tables
        -- ==========================================

        CREATE TABLE IF NOT EXISTS Recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            instructions TEXT,
            expiration_duration DATETIME,
            is_countable BOOLEAN NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS Recipe_Ingredients (
            recipe_id INTEGER,
            ingredient_id INTEGER,
            amount_grams REAL NOT NULL,
            PRIMARY KEY (recipe_id, ingredient_id),
            FOREIGN KEY (recipe_id) REFERENCES Recipes(id),
            FOREIGN KEY (ingredient_id) REFERENCES Ingredients(id)
        );

        -- ==========================================
        -- 3. Views
        -- ==========================================

        -- Dynamically calculates total recipe nutrients based on ingredient amounts.
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
    conn.close()
    print(f"Database schema created successfully in '{db_name}'!")

# --- Execution ---
if __name__ == "__main__":
    create_schema(DB_PATH)