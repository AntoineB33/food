import sqlite3
import ast
from ingredients_nutrients_db_generator import DB_PATH
from parse_and_match_ingredient_v1 import parse_and_match_ingredient

# db from https://github.com/josephrmartinez/recipe-dataset
SOURCE_DB_PATH = "13k-recipes.db"

TARGET_DB_PATH = DB_PATH


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

def migrate_recipes():
    # 1. Connect to both databases
    source_conn = sqlite3.connect(SOURCE_DB_PATH)
    target_conn = sqlite3.connect(TARGET_DB_PATH)
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    print("Fetching recipes from 13k-recipes.db...")
    
    # The downloaded DB has a table named 'recipes' with columns: Title, Ingredients, Instructions
    try:
        source_cursor.execute("SELECT Title, Ingredients, Instructions FROM recipes")
        rows = source_cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error reading source database. Make sure the file exists and the table name is correct: {e}")
        return
    
    print(f"Found {len(rows)} recipes. Beginning migration...")
    
    recipes_inserted = 0
    
    for row in rows:
        title = row[0]
        ingredients_str_list = row[1]
        instructions = row[2]
        
        # 2. Insert into the target Recipes table
        try:
            target_cursor.execute(
                "INSERT OR IGNORE INTO Recipes (name, instructions) VALUES (?, ?)", 
                (title, instructions)
            )
            
            # Fetch the ID of the recipe we just inserted (or the existing one)
            target_cursor.execute("SELECT id FROM Recipes WHERE name = ?", (title,))
            recipe_id_row = target_cursor.fetchone()
            
            if not recipe_id_row:
                continue 
                
            recipe_id = recipe_id_row[0]
            recipes_inserted += 1
            
            # 3. Parse and Insert Ingredients (The NLP challenge)
            # The downloaded dataset stores ingredients as a stringified list:
            # "['2 large Italian eggplants', '1 tablespoon canola oil']"
            if ingredients_str_list:
                try:
                    # Safely convert the string representation into an actual Python list
                    ingredient_list = ast.literal_eval(ingredients_str_list)
                    
                    for raw_ingredient_string in ingredient_list:
                        # Attempt to extract the USDA ID and grams from the raw text
                        usda_id, amount_grams = parse_and_match_ingredient(raw_ingredient_string, target_cursor)
                        
                        if usda_id and amount_grams:
                            target_cursor.execute("""
                                INSERT OR IGNORE INTO Recipe_Ingredients (recipe_id, ingredient_id, amount_grams)
                                VALUES (?, ?, ?)
                            """, (recipe_id, usda_id, amount_grams))
                            
                except (ValueError, SyntaxError):
                    print(f"Could not parse ingredient list for recipe: {title}")

        except sqlite3.Error as e:
            print(f"Database error for recipe '{title}': {e}")
            
    target_conn.commit()
    
    source_conn.close()
    target_conn.close()
    
    print(f"\nMigration complete! Inserted {recipes_inserted} recipes into your database.")

if __name__ == "__main__":
    expand_database_with_recipes(TARGET_DB_PATH)
    migrate_recipes()