import re
import sqlite3

# Basic conversion table (volume/weight to grams)
# Note: This is an approximation. True accuracy requires density lookups per ingredient.
UNIT_TO_GRAMS = {
    'cup': 240, 'cups': 240, 'c': 240,
    'tablespoon': 15, 'tablespoons': 15, 'tbsp': 15, 'tbs': 15,
    'teaspoon': 5, 'teaspoons': 5, 'tsp': 5,
    'ounce': 28.35, 'ounces': 28.35, 'oz': 28.35,
    'pound': 453.59, 'pounds': 453.59, 'lb': 453.59, 'lbs': 453.59,
    'gram': 1, 'grams': 1, 'g': 1,
    'kilogram': 1000, 'kilograms': 1000, 'kg': 1000,
    'clove': 5, 'cloves': 5, # e.g., garlic
    'pinch': 0.36
}

def parse_qty(qty_str):
    """Safely converts strings like '1', '1/2', or '1 1/2' into floats."""
    try:
        parts = qty_str.strip().split()
        if len(parts) == 2:
            num, den = parts[1].split('/')
            return float(parts[0]) + (float(num) / float(den))
        elif '/' in parts[0]:
            num, den = parts[0].split('/')
            return float(num) / float(den)
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return 1.0  # Fallback quantity

def parse_and_match_ingredient(raw_string, target_cursor):
    # 1. Extract Quantity, Unit, and Ingredient Name
    # Matches patterns like "1 1/2 cups all-purpose flour"
    match = re.match(r'^([\d\s\.\/]+)\s*([a-zA-Z]+)?\s+(.*)$', raw_string.strip())
    
    if not match:
        return None, None
        
    qty_str, unit_str, ingredient_name = match.groups()
    
    # 2. Parse the quantity into a float
    quantity = parse_qty(qty_str)
    
    # 3. Convert to Grams
    amount_grams = quantity
    unit = unit_str.lower() if unit_str else None
    
    if unit in UNIT_TO_GRAMS:
        amount_grams = quantity * UNIT_TO_GRAMS[unit]
    else:
        # If no recognized unit (e.g., "2 large eggplants"), fallback to a default weight
        # You can expand this logic later to handle unitless whole foods.
        amount_grams = quantity * 100 
        
        # If the regex grouped part of the name into the unit, reconstruct it
        if unit_str: 
            ingredient_name = f"{unit_str} {ingredient_name}"

    # Clean up the ingredient name (remove common adjectives like "large", "chopped")
    clean_name = re.sub(r'\b(large|medium|small|chopped|diced|fresh|minced)\b', '', ingredient_name, flags=re.IGNORECASE).strip()

    # 4. Search your USDA 'Ingredients' table
    # Using basic fuzzy matching. The % signs act as wildcards.
    try:
        target_cursor.execute(
            "SELECT id FROM Ingredients WHERE name LIKE ? LIMIT 1", 
            (f"%{clean_name}%",)
        )
        row = target_cursor.fetchone()
        
        if row:
            return row[0], round(amount_grams, 2)
            
    except sqlite3.Error as e:
        print(f"Database error during ingredient lookup: {e}")

    # No match found
    return None, None