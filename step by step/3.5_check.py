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
    # 0. Read and validate clipboard input FIRST
    try:
        clipboard_text = pyperclip.paste().strip()
    except pyperclip.PyperclipException:
        raise RuntimeError("Could not read from the clipboard.")

    if not clipboard_text:
        raise ValueError("Clipboard is empty. Please copy a valid CSV before running the script.")

    # Validate CSV and required columns
    required_columns = {'id', 'fdc_id', 'nutrient_id', 'amount', 'data_points', 'derivation_id', 'min', 'max', 'median'}
    try:
        f_in = io.StringIO(clipboard_text)
        reader = csv.reader(f_in)
        header = next(reader)
        header_cleaned = [col.strip() for col in header]
        
        missing_cols = required_columns - set(header_cleaned)
        if missing_cols:
            raise ValueError(f"Clipboard text is missing required CSV columns: {', '.join(missing_cols)}")
    except StopIteration:
        raise ValueError("Clipboard text does not contain a valid CSV header.")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError("Clipboard text could not be parsed as CSV.") from e

    # 1. Define file paths
    last_checked_path = Path(r"step by step bats\last_checked_food.txt")
    food_manual_path = Path(r"DB\food_manual.csv")

    # 2. Check if the target food file has content
    target_food = None
    if last_checked_path.exists():
        content = last_checked_path.read_text(encoding='utf-8').strip()
        if content:
            target_food = content

    combined_text = ""

    # 3. Process the food manual file
    if not target_food:
        # --- PATH A: last_checked_food.txt is empty or missing (Take whole files) ---
        print("No specific food requested (file is empty). Taking whole files.")
        
        combined_text += f"--- START OF {food_manual_path} ---\n"
        combined_text += get_full_file_content(food_manual_path)
        combined_text += f"\n--- END OF {food_manual_path} ---\n\n"
        
    else:
        # --- PATH B: Target food provided (Filter the files) ---
        target_food_lower = target_food.lower()
        print(f"Filtering files starting from: '{target_food}'")
        
        # Filter DB\food_manual.csv
        if not food_manual_path.exists():
            raise FileNotFoundError(f"Required file not found: {food_manual_path}")

        filtered_foods = []
        found_food = False

        with food_manual_path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                food_header = next(reader)
                filtered_foods.append(food_header)
            except StopIteration:
                raise ValueError(f"{food_manual_path} is empty.")

            for row in reader:
                if not found_food and any(target_food_lower == cell.strip().lower() for cell in row):
                    found_food = True
                
                if found_food:
                    filtered_foods.append(row)

        if not found_food:
            raise ValueError(f"Food description '{target_food}' was not found in {food_manual_path}.")

        combined_text += f"--- START OF {food_manual_path} ---\n"
        combined_text += rows_to_csv_string(filtered_foods)
        combined_text += f"--- END OF {food_manual_path} ---\n\n"

    # 4. Insert the clipboard content (Replacing food_nutrient_manual.csv)
    combined_text += "--- START OF the suggested nutrient composition ---\n"
    combined_text += clipboard_text
    combined_text += "\n--- END OF the suggested nutrient composition ---\n\n"

    # 6. Define the custom text in the main block
    custom_main_text = """
Is the nutrient composition correct? If not, write the whole corrected csv.
"""

    final_output = combined_text + custom_main_text.strip()

    # 7. Write back to clipboard
    try:
        pyperclip.copy(final_output)
        print("Successfully copied the final prompt to the clipboard!")
    except pyperclip.PyperclipException:
        print("Error: Could not find a copy/paste mechanism for your system.")