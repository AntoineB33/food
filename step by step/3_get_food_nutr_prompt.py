import csv
import io
import os
import pyperclip

def get_existing_ids(file_paths):
    """
    Reads the provided CSV files and extracts all existing fdc_ids into a set.
    """
    existing_ids = set()
    
    for path in file_paths:
        if not os.path.exists(path):
            print(f"Warning: The file '{path}' was not found. Skipping...")
            continue
            
        try:
            with open(path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                # Try to get the header to find the fdc_id column index
                header = next(reader, None)
                if not header:
                    continue
                
                # Default to column 0, but check if header explicitly names it
                id_index = header.index("fdc_id") if "fdc_id" in header else 0
                
                for row in reader:
                    if row and len(row) > id_index and row[id_index].isdigit():
                        existing_ids.add(int(row[id_index]))
        except (OSError, UnicodeError) as e:
            print(f"Error reading {path}: {e}")
            
    return existing_ids

def generate_new_food_prompt(db_paths, food_manual_path, daily_need_path, constant_text):
    # 1. Read the daily need table text
    daily_need_text = ""
    if os.path.exists(daily_need_path):
        try:
            with open(daily_need_path, 'r', encoding='utf-8') as f:
                daily_need_text = f.read().strip()
        except (OSError, UnicodeError) as e:
            print(f"Error reading {daily_need_path}: {e}")
    else:
        print(f"Warning: The file '{daily_need_path}' was not found. Continuing without it.")

    # 2. Get clipboard content and analyze for errors
    clipboard_content = pyperclip.paste()
    normalized_content = clipboard_content.replace('\r\n', '\n').strip('\n')
    lines = normalized_content.split('\n') if normalized_content else []
    
    if not normalized_content:
        raise ValueError("Clipboard is empty or contains no valid text.")

    descriptions = []
    for i, line in enumerate(lines, start=1):
        if not line or line.isspace():
            raise ValueError(f"Blank line detected at line {i}. Please fix the clipboard input.")
        if line[0].isspace():
            raise ValueError(f"Line {i} starts with a blank character. Please fix the clipboard input.")
        
        descriptions.append(line.strip())

    print("\n--- Clipboard Content Accepted ---")
    print(clipboard_content)
    print("----------------------------------\n")

    new_records = []
    
    if descriptions:
        # 3. Get all existing IDs from the databases
        existing_ids = get_existing_ids(db_paths)
        
        # 4. Generate new records with the smallest possible IDs
        current_id = 1
        for desc in descriptions:
            while current_id in existing_ids:
                current_id += 1
                
            new_records.append([current_id, desc])
            existing_ids.add(current_id) 
            
        # 5. Append the new records to DB\food_manual.csv
        try:
            file_exists = os.path.exists(food_manual_path)
            with open(food_manual_path, 'a', encoding='utf-8', newline='') as f_manual:
                csv_writer = csv.writer(f_manual, quoting=csv.QUOTE_MINIMAL)
                if not file_exists:
                    csv_writer.writerow(["fdc_id", "description"])
                csv_writer.writerows(new_records)
            print(f"Successfully appended {len(new_records)} items to '{food_manual_path}'.")
        except (OSError, UnicodeError) as e:
            print(f"Error writing to {food_manual_path}: {e}")

    # 6. Read the entire content of food_manual.csv to include in the prompt
    full_manual_content = ""
    if os.path.exists(food_manual_path):
        try:
            with open(food_manual_path, 'r', encoding='utf-8') as f_manual:
                full_manual_content = f_manual.read().strip()
        except (OSError, UnicodeError) as e:
            print(f"Error reading {food_manual_path}: {e}")

    # 7. Construct the final text for the clipboard
    parts = []
    if daily_need_text:
        parts.append(daily_need_text)
        
    if full_manual_content:
        # Adds the file name and full CSV content wrapped in markdown block
        parts.append(f"{os.path.basename(food_manual_path)}\n```csv\n{full_manual_content}\n```")
        
    if constant_text:
        parts.append(constant_text)
        
    # Join everything with double newlines
    formatted_text = "\n\n".join(parts)
    
    if formatted_text:
        pyperclip.copy(formatted_text)
        print("New prompt has been copied to your clipboard.")
    else:
        print("No text generated to copy to clipboard.")

if __name__ == "__main__":
    # --- Configuration ---
    food_manual_file = r"DB\food_manual.csv"
    
    # Paths to check for existing IDs
    database_files = [
        r"DB\food.csv",
        food_manual_file
    ]
    
    # Path to the daily need table
    daily_need_file = r"DB\daily_need_table.txt"
    
    # Text to append underneath the generated CSV table
    my_constant_text = """For each food item of this list, give a value for all the needed nutrients. Write a text easy to copy in a csv format with those columns:
"id","fdc_id","nutrient_id","amount","data_points","derivation_id","min","max","median","footnote","min_year_acquired"
This is supposed to be an extension of food_nutrient.csv from the SR Legacy from fdc.nal.usda.gov. Use the corresponding IDs from SR Legacy and food_manual.csv"""

    generate_new_food_prompt(database_files, food_manual_file, daily_need_file, my_constant_text)