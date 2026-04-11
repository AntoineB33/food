to get the database ingredients_nutrients.db (ingredients - nutrients) :
- download "Foundation Foods December 2025 (CSV)" in https://fdc.nal.usda.gov/download-datasets/ and place the extracted folder in the project root
- do the same with the 13k-recipes.db file in https://github.com/josephrmartinez/recipe-dataset
- run ingredients_nutrients.py then recipes_nutrients_db_generator.py to create ingredients_nutrients.db.


`ingredients_nutrients.db` is a relational database containing tables for USDA foundation foods and user-defined recipes, alongside dynamic views for nutritional calculations.

### Core USDA Tables
* **`Ingredients`**: Stores food items (ID and name).
* **`Nutrients`**: Stores nutrient definitions (ID, name, and measurement unit).
* **`Ingredient_Nutrients`**: A junction table that records the exact amount of specific nutrients contained within each 100g of an ingredient.

### Recipe Management Tables
* **`Recipes`**: Stores custom recipes (ID, name, and preparation instructions).
* **`Recipe_Ingredients`**: A junction table linking recipes to ingredients, recording the specific `amount_grams` of each ingredient used in a recipe.

### Dynamic Views
* **`Recipe_Nutrients`**: A virtual table (SQL VIEW) that automatically aggregates and calculates the total nutritional profile of a recipe on the fly based on its constituent ingredients and their respective weights.