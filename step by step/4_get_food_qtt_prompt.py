import csv
import io
import os
import re

import pyperclip


def extract_csv_from_text(text):
    """
    Extracts CSV data from a string, handling optional markdown backticks.
    """
    if not text.strip():
        raise ValueError("Clipboard is empty or contains no text.")
        
    # Look for a markdown csv block (e.g., ```csv ... ```)
    match = re.search(r'```(?:csv)?\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    # Fallback: assume the whole clipboard is the CSV text
    return text.strip()

def append_to_nutrient_manual(csv_string, filepath):
    """
    Parses the CSV string, strictly validates the columns and format, 
    and appends the rows to the nutrient manual file.
    """
    f_in = io.StringIO(csv_string)
    reader = csv.reader(f_in)
    rows = list(reader)

    if not rows:
        raise ValueError("The parsed CSV data is empty.")

    # Define the exact expected columns
    expected_header = [
        "id", "fdc_id", "nutrient_id", "amount", "data_points",
        "derivation_id", "min", "max", "median"
    ]
    
    # Extract and normalize the first row to check if columns match exactly
    actual_header = [str(c).strip().lower() for c in rows[0]]
    
    if actual_header != expected_header:
        raise ValueError(
            f"CSV Column Mismatch!\n"
            f"Expected: {expected_header}\n"
            f"Found:    {actual_header}"
        )

    data_rows = rows[1:]

    if not data_rows:
        raise ValueError("No data rows found in the CSV (only header).")

    # Validate that every row has the correct number of columns (validates CSV format)
    expected_length = len(expected_header)
    for i, row in enumerate(data_rows, start=2): # start=2 because row 1 is the header
        if len(row) != expected_length:
            raise ValueError(
                f"Malformed CSV format at row {i}: expected {expected_length} columns, but found {len(row)}.\n"
                f"Row data: {row}"
            )

    file_exists = os.path.exists(filepath)

    # Write to file (letting OS/IO errors raise naturally)
    with open(filepath, 'a', encoding='utf-8', newline='') as f_out:
        writer = csv.writer(f_out, quoting=csv.QUOTE_MINIMAL)
        # Write header if the file doesn't exist yet
        if not file_exists:
            writer.writerow(expected_header)
        # Append the new records
        writer.writerows(data_rows)
        
    print(f"Successfully appended {len(data_rows)} nutrient records to '{filepath}'.")
    return True

def generate_next_prompt(food_manual_path, daily_need_path, constant_text):
    """
    Reads the daily needs table and the food manual, then constructs a new prompt.
    """
    # 1. Read the daily need table text
    daily_need_text = ""
    if os.path.exists(daily_need_path):
        with open(daily_need_path, 'r', encoding='utf-8') as f:
            daily_need_text = f.read().strip()
    else:
        print(f"Warning: The file '{daily_need_path}' was not found. Continuing without it.")

    # 2. Read the food manual text
    if not os.path.exists(food_manual_path):
        raise FileNotFoundError(f"The required file '{food_manual_path}' was not found.")

    with open(food_manual_path, 'r', encoding='utf-8') as f:
        food_manual_content = f.read().strip()

    # 3. Build the prompt parts
    parts = []
    
    if daily_need_text:
        parts.append(daily_need_text)
        
    parts.append(f"```csv\n{food_manual_content}\n```")
    
    if constant_text:
        parts.append(constant_text)
        
    return "\n\n".join(parts)

if __name__ == "__main__":
    # --- Configuration ---
    nutrient_manual_file = r"DB\food_nutrient_manual.csv"
    food_manual_file = r"DB\food_manual.csv"
    daily_need_file = r"DB\daily_need_table.txt"
    
    # Text to append underneath the food_manual list for the new prompt
    my_next_prompt_text = """Provide me with two columns: food ID and quantity. For each food item (including prepared meals) on your menu, use the corresponding ID from SR Legacy 2018 (fdc.nal.usda.gov) and food_manual.csv (an extension of the main food database), and enter the quantity as a unitless number in the food's unit of measurement (from the same database). Do not include ingredients for prepared meals unless they are also listed as individual items on your menu."""

    # 1. Get the LLM's CSV response from the clipboard
    clipboard_content = pyperclip.paste()
    
    # Show the clipboard text to the user
    print("\n" + "="*40)
    print("CURRENT CLIPBOARD TEXT:")
    print("="*40)
    print(clipboard_content)
    print("="*40 + "\n")
    
    # Ask the user whether to proceed
    choice = input("Do you want to process and append the above clipboard text? (y/n): ").strip().lower()
    
    if choice in ['y', 'yes']:
        # 2. Extract the CSV text
        csv_data = extract_csv_from_text(clipboard_content)
        
        # 3. Append and STRICTLY validate the data
        # (If anything is wrong, a ValueError will be thrown here and stop execution)
        append_to_nutrient_manual(csv_data, nutrient_manual_file)
    else:
        print("Skipping clipboard text processing...")

    # 4. Generate the next prompt and copy to clipboard
    new_prompt = generate_next_prompt(food_manual_file, daily_need_file, my_next_prompt_text)
    pyperclip.copy(new_prompt)
    print("The new prompt has been copied to your clipboard.")