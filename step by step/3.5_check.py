import csv
import io
from pathlib import Path

import pyperclip


def rows_to_csv_string(rows):
    """Converts a list of row lists back into a raw CSV formatted string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerows(rows)
    return output.getvalue()

def get_full_file_content(filepath):
    """Reads and returns the content of a file completely."""
    path = Path(filepath)
    if path.exists():
        return path.read_text(encoding='utf-8')
    return f"[File not found: {filepath}]"

if __name__ == "__main__":
    # 1. Define file paths
    last_checked_path = Path(r"step by step bats\last_checked_food.txt")
    food_manual_path = Path(r"DB\food_manual.csv")
    food_nutrient_path = Path(r"DB\food_nutrient_manual.csv")
    nutrient_path = Path(r"DB\nutrient.csv")

    # 2. Check if the target food file has content
    target_food = None
    if last_checked_path.exists():
        content = last_checked_path.read_text(encoding='utf-8').strip()
        if content:
            target_food = content

    combined_text = ""

    # 3. Process the food and nutrient manual files
    if not target_food:
        # --- PATH A: last_checked_food.txt is empty or missing (Take whole files) ---
        print("No specific food requested (file is empty). Taking whole files.")
        
        combined_text += f"--- START OF {food_manual_path} ---\n"
        combined_text += get_full_file_content(food_manual_path)
        combined_text += f"\n--- END OF {food_manual_path} ---\n\n"
        
        combined_text += f"--- START OF {food_nutrient_path} ---\n"
        combined_text += get_full_file_content(food_nutrient_path)
        combined_text += f"\n--- END OF {food_nutrient_path} ---\n\n"
        
    else:
        # --- PATH B: Target food provided (Filter the files) ---
        target_food_lower = target_food.lower()
        print(f"Filtering files starting from: '{target_food}'")
        
        # Filter DB\food_manual.csv
        if not food_manual_path.exists():
            raise FileNotFoundError(f"Required file not found: {food_manual_path}")

        filtered_foods = []
        valid_food_ids = set()
        found_food = False

        with food_manual_path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                food_header = next(reader)
                filtered_foods.append(food_header)
                id_col_idx = food_header.index('fdc_id') if 'fdc_id' in food_header else 0
            except StopIteration:
                raise ValueError(f"{food_manual_path} is empty.")

            for row in reader:
                if not found_food and any(target_food_lower == cell.strip().lower() for cell in row):
                    found_food = True
                
                if found_food:
                    filtered_foods.append(row)
                    if len(row) > id_col_idx:
                        valid_food_ids.add(row[id_col_idx])

        if not found_food:
            raise ValueError(f"Food description '{target_food}' was not found in {food_manual_path}.")

        combined_text += f"--- START OF {food_manual_path} ---\n"
        combined_text += rows_to_csv_string(filtered_foods)
        combined_text += f"--- END OF {food_manual_path} ---\n\n"

        # Filter DB\food_nutrient_manual.csv
        if not food_nutrient_path.exists():
            raise FileNotFoundError(f"Required file not found: {food_nutrient_path}")

        filtered_nutrients = []
        with food_nutrient_path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                nut_header = next(reader)
                filtered_nutrients.append(nut_header)
                
                # Figure out ID column index safely
                if 'fdc_id' in nut_header:
                    fn_id_col = nut_header.index('fdc_id')
                elif 'food_id' in nut_header:
                    fn_id_col = nut_header.index('food_id')
                else:
                    fn_id_col = 1 if len(nut_header) > 1 else 0
            except StopIteration:
                pass 

            for row in reader:
                if len(row) > fn_id_col and row[fn_id_col] in valid_food_ids:
                    filtered_nutrients.append(row)

        combined_text += f"--- START OF {food_nutrient_path} ---\n"
        combined_text += rows_to_csv_string(filtered_nutrients)
        combined_text += f"--- END OF {food_nutrient_path} ---\n\n"

    # 4. Add the full nutrient.csv (always included entirely)
    combined_text += f"--- START OF {nutrient_path} ---\n"
    combined_text += get_full_file_content(nutrient_path)
    combined_text += f"\n--- END OF {nutrient_path} ---\n\n"

    # 5. Define the custom text in the main block
    custom_main_text = """
Is the nutrient composition described in DB\food_nutrient_manual.csv correct? If not, write the whole corrected file.
"""

    final_output = combined_text + custom_main_text.strip()

    # 6. Write to clipboard
    try:
        pyperclip.copy(final_output)
        print("Successfully copied data to the clipboard!")
    except pyperclip.PyperclipException:
        print("Error: Could not find a copy/paste mechanism for your system.")