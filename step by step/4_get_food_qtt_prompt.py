import csv
import os

import pyperclip

# ==========================================
# CONFIGURATION - Modify these paths as needed
# ==========================================
FOOD_MANUAL_CSV_PATH = 'DB/food_manual.csv'
FOOD_CSV_PATH = 'DB/food.csv'

# Modify the prompt text that gets appended at the end of the clipboard output
PROMPT_TEXT = """Provide me with two columns: food ID and quantity. For each food item, use the corresponding ID from SR Legacy 2018 (fdc.nal.usda.gov) and food_manual.csv, and enter the quantity as a unitless number in the food's unit of measurement (from the same database).
It must be in a csv format, easy to copy."""
# ==========================================

def get_existing_ids():
    """Reads both CSVs and returns a set of all existing integer FDC IDs."""
    existing_ids = set()

    # Read SR Legacy food.csv
    if os.path.exists(FOOD_CSV_PATH):
        with open(FOOD_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    if 'fdc_id' in row:
                        existing_ids.add(int(row['fdc_id']))
                except ValueError:
                    pass # Ignore non-integer IDs if any exist

    # Read food_manual.csv
    if os.path.exists(FOOD_MANUAL_CSV_PATH):
        with open(FOOD_MANUAL_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    if 'fdc_id' in row:
                        existing_ids.add(int(row['fdc_id']))
                except ValueError:
                    pass
                    
    return existing_ids

def main():
    # 1. Get food items from clipboard
    clipboard_content = pyperclip.paste()
    new_items = [line.strip() for line in clipboard_content.strip().split('\n') if line.strip()]

    if not new_items:
        print("No food items found in the clipboard. Exiting...")
        return

    # 2. Get existing IDs to ensure uniqueness
    existing_ids = get_existing_ids()
    
    # Start our new IDs at 1 higher than the maximum existing ID.
    # If no IDs exist yet, default to starting at 9000000.
    next_id = max(existing_ids) + 1 if existing_ids else 9000000

    # 3. Append new items to food_manual.csv
    file_exists = os.path.exists(FOOD_MANUAL_CSV_PATH)
    
    with open(FOOD_MANUAL_CSV_PATH, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if creating a new file
        if not file_exists:
            writer.writerow(['fdc_id', 'description'])
        
        # Add each new item with a unique ID
        for item in new_items:
            writer.writerow([next_id, item])
            next_id += 1
            
    print(f"Added {len(new_items)} new items to {FOOD_MANUAL_CSV_PATH}.")

    # 4. Format the final output (just the vertical list of new items + prompt)
    vertical_list = "\n".join(new_items)
    final_output = f"{vertical_list}\n\n{PROMPT_TEXT}"

    # 5. Copy to clipboard
    pyperclip.copy(final_output)
    print("The food list and prompt have been copied to your clipboard!")

if __name__ == "__main__":
    main()