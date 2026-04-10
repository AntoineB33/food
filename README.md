to get the database ingredients_nutrients.db (ingredients - nutrients) :
- download Foundation Foods December 2025 (CSV) in https://fdc.nal.usda.gov/download-datasets/ and place the extracted folder in the project root
- run ingredients_nutrients.py to create ingredients_nutrients.db.


ingredients_nutrients.db is a relational database with three linked tables:

* **`Ingredients`**: Stores food items (ID and name).
* **`Nutrients`**: Stores nutrient definitions (ID, name, and measurement unit).
* **`Ingredient_Nutrients`**: A junction table that records the exact amount of specific nutrients contained within each ingredient.