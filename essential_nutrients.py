import pandas as pd

from ingredients_nutrients import NUTRIENT_DEF_CSV_PATH


essential_nutrients = [
    # Water (1)
    "Water",
    
    # Essential Fatty Acids (2)
    "Alpha-linolenic acid",
    "Linoleic acid",
    
    # Essential Amino Acids (9)
    "Histidine",
    "Isoleucine",
    "Leucine",
    "Lysine",
    "Methionine",
    "Phenylalanine",
    "Threonine",
    "Tryptophan",
    "Valine",
    
    # Vitamins & Vitamin-like Compounds (14)
    "Vitamin A (Retinol)",
    "Vitamin C (Ascorbic acid)",
    "Vitamin D",
    "Vitamin E",
    "Vitamin K",
    "Vitamin B1 (Thiamin)",
    "Vitamin B2 (Riboflavin)",
    "Vitamin B3 (Niacin)",
    "Vitamin B5 (Pantothenic acid)",
    "Vitamin B6 (Pyridoxine)",
    "Vitamin B7 (Biotin)",
    "Vitamin B9 (Folate)",
    "Vitamin B12 (Cobalamin)",
    "Choline",
    
    # Essential Minerals - Macrominerals (7)
    "Calcium",
    "Chloride",
    "Magnesium",
    "Phosphorus",
    "Potassium",
    "Sodium",
    "Sulfur",
    
    # Essential Minerals - Trace Minerals (9)
    "Chromium",
    "Copper",
    "Fluoride",
    "Iodine",
    "Iron",
    "Manganese",
    "Molybdenum",
    "Selenium",
    "Zinc"
]

usda_nutrient_mapping = {
    # Water
    "Water": "Water",
    
    # Essential Fatty Acids
    "Alpha-linolenic acid": "PUFA 18:3 n-3 c,c,c (ALA)",
    "Linoleic acid": "PUFA 18:2 n-6 c,c",
    
    # Essential Amino Acids
    "Histidine": "Histidine",
    "Isoleucine": "Isoleucine",
    "Leucine": "Leucine",
    "Lysine": "Lysine",
    "Methionine": "Methionine",
    "Phenylalanine": "Phenylalanine",
    "Threonine": "Threonine",
    "Tryptophan": "Tryptophan",
    "Valine": "Valine",
    
    # Vitamins & Vitamin-like Compounds
    "Vitamin A (Retinol)": "Retinol",
    "Vitamin C (Ascorbic acid)": "Vitamin C, total ascorbic acid",
    "Vitamin D": "Vitamin D (D2 + D3)",
    "Vitamin E": "Vitamin E (alpha-tocopherol)",
    "Vitamin K": "Vitamin K (phylloquinone)",
    "Vitamin B1 (Thiamin)": "Thiamin",
    "Vitamin B2 (Riboflavin)": "Riboflavin",
    "Vitamin B3 (Niacin)": "Niacin",
    "Vitamin B5 (Pantothenic acid)": "Pantothenic acid",
    "Vitamin B6 (Pyridoxine)": "Vitamin B-6",
    "Vitamin B7 (Biotin)": "Biotin",
    "Vitamin B9 (Folate)": "Folate, total",
    "Vitamin B12 (Cobalamin)": "Vitamin B-12",
    "Choline": "Choline, total",
    
    # Essential Minerals - Macrominerals
    "Calcium": "Calcium, Ca",
    "Chloride": "Chlorine, Cl",
    "Magnesium": "Magnesium, Mg",
    "Phosphorus": "Phosphorus, P",
    "Potassium": "Potassium, K",
    "Sodium": "Sodium, Na",
    "Sulfur": "Sulfur, S",
    
    # Essential Minerals - Trace Minerals
    "Chromium": "Chromium, Cr",
    "Copper": "Copper, Cu",
    "Fluoride": "Fluoride, F",
    "Iodine": "Iodine, I",
    "Iron": "Iron, Fe",
    "Manganese": "Manganese, Mn",
    "Molybdenum": "Molybdenum, Mo",
    "Selenium": "Selenium, Se",
    "Zinc": "Zinc, Zn"
}

unit_names = {
    "Water": "g",
    "Alpha-linolenic acid": "g",
    "Linoleic acid": "g",
    "Histidine": "g",
    "Isoleucine": "g",
    "Leucine": "g",
    "Lysine": "g",
    "Methionine": "g",
    "Phenylalanine": "g",
    "Threonine": "g",
    "Tryptophan": "g",
    "Valine": "g",
    "Vitamin A (Retinol)": "µg",
    "Vitamin C (Ascorbic acid)": "mg",
    "Vitamin D": "µg",
    "Vitamin E": "mg",
    "Vitamin K": "µg",
    "Vitamin B1 (Thiamin)": "mg",
    "Vitamin B2 (Riboflavin)": "mg",
    "Vitamin B3 (Niacin)": "mg",
    "Vitamin B5 (Pantothenic acid)": "mg",
    "Vitamin B6 (Pyridoxine)": "mg",
    "Vitamin B7 (Biotin)": "µg",
    "Vitamin B9 (Folate)": "µg",
    "Vitamin B12 (Cobalamin)": "µg",
    "Choline": "mg",
    "Calcium": "mg",
    "Chloride": "mg",
    "Magnesium": "mg",
    "Phosphorus": "mg",
    "Potassium": "mg",
    "Sodium": "mg",
    'Sulfur': 'mg',
    'Chromium': 'µg',
    'Copper': 'mg',
    'Fluoride': 'mg',
    'Iodine': 'µg',
    'Iron': 'mg',
    'Manganese': 'mg',
    'Molybdenum': 'µg',
    'Selenium': 'µg',
    'Zinc': 'mg'
}


# Nutrient intervals formatted as (min, max) in the units specified by the user
daily_nutrient_intervals = {
    # Water (1) - Adjusted higher for daily walks, boxing, and lifting (in grams/mL)
    "Water": (3700, 4500),
    
    # Essential Fatty Acids (2)
    "Alpha-linolenic acid": (1.6, 3.0),
    "Linoleic acid": (17.0, 25.0),
    
    # Essential Amino Acids (9) - Minimums scaled to an 80 kg male
    "Histidine": (0.8, 3.0),
    "Isoleucine": (1.6, 4.0),
    "Leucine": (3.1, 8.0),   # Crucial for muscle protein synthesis recovery
    "Lysine": (2.4, 7.0),
    "Methionine": (1.2, 3.0),
    "Phenylalanine": (2.0, 5.0),
    "Threonine": (1.2, 3.0),
    "Tryptophan": (0.3, 1.0),
    "Valine": (2.1, 5.0),
    
    # Vitamins & Vitamin-like Compounds (14)
    "Vitamin A (Retinol)": (900, 3000),
    "Vitamin C (Ascorbic acid)": (90, 2000),
    "Vitamin D": (15, 100),
    "Vitamin E": (15, 1000),
    "Vitamin K": (120, 1000), # No formal UL, but safe upper practical range
    "Vitamin B1 (Thiamin)": (1.2, 3.0),
    "Vitamin B2 (Riboflavin)": (1.3, 3.0),
    "Vitamin B3 (Niacin)": (16, 35),
    "Vitamin B5 (Pantothenic acid)": (5, 10),
    "Vitamin B6 (Pyridoxine)": (1.3, 100),
    "Vitamin B7 (Biotin)": (30, 100),
    "Vitamin B9 (Folate)": (400, 1000),
    "Vitamin B12 (Cobalamin)": (2.4, 10), # No UL, but safe upper practical range
    "Choline": (550, 3500),
    
    # Essential Minerals - Macrominerals (7)
    "Calcium": (1000, 2500),
    "Chloride": (2300, 3600),
    "Magnesium": (400, 700),  # Upper end helpful for muscular recovery
    "Phosphorus": (700, 4000),
    "Potassium": (3400, 4700),
    "Sodium": (1500, 3000),   # Upper end accounts for sweat depletion
    "Sulfur": (800, 1500),    # Derived largely from methionine and cysteine
    
    # Essential Minerals - Trace Minerals (9)
    "Chromium": (35, 100),
    "Copper": (0.9, 10),
    "Fluoride": (4, 10),
    "Iodine": (150, 1100),
    "Iron": (8, 45),
    "Manganese": (2.3, 11),
    "Molybdenum": (45, 2000),
    "Selenium": (55, 400),
    "Zinc": (11, 40)
}

if __name__ == "__main__":
    # check if all values in usda_nutrient_mapping are present in FoodData_Central_foundation_food_csv_2025-12-18\FoodData_Central_foundation_food_csv_2025-12-18\nutrient.csv
    usda_nutrients = set(pd.read_csv(NUTRIENT_DEF_CSV_PATH)['name'])
    for nutrient in usda_nutrient_mapping.values():
        if nutrient not in usda_nutrients:
            print(f"Warning: '{nutrient}' from USDA mapping is not found in the nutrient definitions CSV.")
