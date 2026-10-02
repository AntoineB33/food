import os
import csv
import io
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

    # 2. Get clipboard content (the vertical list of food descriptions)
    clipboard_content = pyperclip.paste()
    if not clipboard_content.strip():
        print("Error: Clipboard is empty or contains no text.")
        return
        
    # Split by newline and remove empty lines/extra whitespace
    descriptions = [line.strip() for line in clipboard_content.split('\n') if line.strip()]
    if not descriptions:
        print("Error: No valid food descriptions found in the clipboard.")
        return

    # 3. Get all existing IDs from the databases
    existing_ids = get_existing_ids(db_paths)
    
    # 4. Generate new records with the smallest possible IDs
    new_records = []
    current_id = 1
    
    for desc in descriptions:
        # Increment current_id until we find one not in the database
        while current_id in existing_ids:
            current_id += 1
            
        new_records.append([current_id, desc])
        existing_ids.add(current_id) # Mark this new ID as used for the next iteration
        
    # 5. Format the output as a CSV string
    output_stream = io.StringIO()
    writer = csv.writer(output_stream, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
    
    # Write Header
    writer.writerow(["fdc_id", "description"])
    # Write Rows
    writer.writerows(new_records)
    
    csv_string = output_stream.getvalue().strip()
    
    # 6. Append the new records to DB\food_manual.csv
    try:
        # Check if file exists so we know whether to write the header
        file_exists = os.path.exists(food_manual_path)
        
        # 'a' mode appends to the file, newline='' prevents double-spacing on Windows
        with open(food_manual_path, 'a', encoding='utf-8', newline='') as f_manual:
            csv_writer = csv.writer(f_manual, quoting=csv.QUOTE_MINIMAL)
            if not file_exists:
                csv_writer.writerow(["fdc_id", "description"])
            csv_writer.writerows(new_records)
        print(f"Successfully appended {len(new_records)} items to '{food_manual_path}'.")
    except Exception as e:
        print(f"Error writing to {food_manual_path}: {e}")

    # 7. Construct the final text for the clipboard (with backticks around the CSV)
    # Build a list of the text parts, filtering out any empty ones
    parts = []
    if daily_need_text:
        parts.append(daily_need_text)
        
    parts.append(f"```csv\n{csv_string}\n```")
    
    if constant_text:
        parts.append(constant_text)
        
    # Join everything with double newlines
    formatted_text = "\n\n".join(parts)
    
    # Copy to clipboard
    pyperclip.copy(formatted_text)
    
    print("New prompt has been copied to your clipboard.")

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
This is supposed to be an extension of food_nutrient.csv from the SR Legacy from fdc.nal.usda.gov."""

    generate_new_food_prompt(database_files, food_manual_file, daily_need_file, my_constant_text)