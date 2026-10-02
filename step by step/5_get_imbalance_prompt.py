import csv
import io
import os
import re
from collections import defaultdict

import pyperclip


def parse_numeric(val_str):
    """Extracts numeric values from strings like '2,350 kcal' or handles 'No limit'."""
    if "No limit" in val_str:
        return float('inf')
    match = re.search(r'([\d,\.]+)', val_str)
    if match:
        return float(match.group(1).replace(',', ''))
    return 0.0

def extract_unit(val_str, numeric_val):
    """Extracts the unit of measurement (e.g., 'kcal', 'mg') from a string."""
    if "No limit" in val_str:
        return ""
    # Remove the numeric part and commas to leave just the unit text
    unit = val_str.replace(str(numeric_val).replace('.0', ''), '').replace(',', '').strip()
    return unit

def load_daily_needs(filepath):
    """Parses the txt file to extract Min, Max, and FDC IDs from brackets [ID1, ID2]."""
    needs = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines[1:]: # Skip header
        if not line.strip(): continue
        
        # Split by 2 or more spaces or tabs
        parts = re.split(r'\s{2,}|\t+', line.strip())
        if len(parts) >= 3:
            raw_name = parts[0].strip()
            
            # Look for IDs enclosed in brackets e.g., [1008] or [1218, 1219]
            id_match = re.search(r'\[([\d,\s]+)\]', raw_name)
            
            if not id_match:
                print(f"Skipping '{raw_name}': No FDC IDs found in brackets (e.g. [1008]).")
                continue
                
            # Parse out the integer IDs
            id_str = id_match.group(1)
            nutrient_ids = [int(i.strip()) for i in id_str.split(',')]
            
            # Clean the display name by removing the brackets and IDs
            clean_name = re.sub(r'\s*\[.*?\]\s*', '', raw_name).strip()
            
            min_val = parse_numeric(parts[1])
            max_val = parse_numeric(parts[2])
            
            # Try to grab unit from min, fallback to max
            unit = extract_unit(parts[1], min_val) or extract_unit(parts[2], max_val)

            needs[clean_name] = {
                "ids": nutrient_ids,
                "min": min_val, 
                "max": max_val, 
                "unit": unit
            }
    return needs

def load_nutrient_db(files):
    """Loads nutrient info into a nested dictionary: {fdc_id: {nutrient_id: amount}}"""
    db = defaultdict(lambda: defaultdict(float))
    for file in files:
        if not os.path.exists(file):
            print(f"Warning: {file} not found. Skipping.")
            continue
        
        with open(file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fdc_id = str(row.get('fdc_id', row.get('id', ''))).strip()
                nut_id = int(row.get('nutrient_id', 0))
                amount = float(row.get('amount', 0))
                
                if fdc_id and nut_id:
                    db[fdc_id][nut_id] = amount
    return db

def extract_clipboard_csv(text):
    """
    Extracts and strictly validates the expected two-column CSV from the clipboard.
    Throws ValueError if the format or columns are wrong.
    """
    if not text.strip():
        raise ValueError("Clipboard is empty or contains no text.")
        
    match = re.search(r'```(?:csv)?\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    csv_text = match.group(1).strip() if match else text.strip()
    
    if not csv_text:
        raise ValueError("No valid CSV content found in the clipboard.")
        
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    
    if not rows:
        raise ValueError("The parsed CSV data is empty.")
        
    # Strictly check column count on the first row
    if len(rows[0]) != 2:
        raise ValueError(
            f"CSV Column Mismatch! Expected exactly 2 columns (Food ID, Quantity), "
            f"but found {len(rows[0])} columns.\nFirst row data: {rows[0]}"
        )
        
    diet = {}
    data_rows_found = 0
    
    for i, row in enumerate(rows):
        if not row:
            continue # Skip empty lines
            
        if len(row) != 2:
            raise ValueError(
                f"Malformed CSV format at row {i+1}: expected 2 columns, but found {len(row)}.\n"
                f"Row data: {row}"
            )
            
        food_id = str(row[0]).strip()
        qty_str = str(row[1]).strip()
        
        try:
            quantity = float(qty_str)
            diet[food_id] = quantity
            data_rows_found += 1
        except ValueError:
            # If it fails on the first row, it's likely just a header, so we can ignore it
            if i == 0:
                continue
            else:
                raise ValueError(
                    f"Invalid quantity '{qty_str}' at row {i+1}. The quantity must be a valid number.\n"
                    f"Row data: {row}"
                )
                
    if data_rows_found == 0:
        raise ValueError("No valid data rows found in the CSV (only header).")
        
    return diet

if __name__ == "__main__":
    # --- Configuration ---
    daily_need_file = r"DB\daily_need_table.txt"
    nutrient_file = r"DB\food_nutrient.csv"
    manual_nutrient_file = r"DB\food_nutrient_manual.csv"

    PORTION_DIVISOR = 100.0 
    
    # 1. Get diet from clipboard (fails instantly if format is wrong)
    clipboard_content = pyperclip.paste()
    diet = extract_clipboard_csv(clipboard_content)
    
    # 2. Load Databases
    print("Loading databases...")
    daily_needs = load_daily_needs(daily_need_file)
    nutrient_db = load_nutrient_db([nutrient_file, manual_nutrient_file])

    # 3. Calculate Totals
    daily_totals = defaultdict(float)
    
    for food_id, quantity in diet.items():
        food_nutrients = nutrient_db.get(food_id, {})
        multiplier = quantity / PORTION_DIVISOR
        
        for nut_id, amount in food_nutrients.items():
            daily_totals[nut_id] += amount * multiplier

    # 4. Compare with dynamic needs and generate report
    report_lines = ["### Nutrition Gap Report\n"]
    lacks = []
    excesses = []
    perfect = []

    for name, limits in daily_needs.items():
        # Sum up all mapped nutrient IDs for this requirement
        total_val = sum(daily_totals[nid] for nid in limits['ids'])
        
        unit = limits['unit']
        min_v = limits['min']
        max_v = limits['max']
        
        max_str = "No limit" if max_v == float('inf') else f"{max_v} {unit}"
        record = f"- **{name}**: {total_val:.1f} {unit} (Target: {min_v} to {max_str})"
        
        if total_val < min_v:
            lacks.append(record)
        elif total_val > max_v:
            excesses.append(record)
        else:
            perfect.append(record)

    if lacks:
        report_lines.append("#### 📉 Lacks (Under Minimum):")
        report_lines.extend(lacks)
        report_lines.append("")
        
    if excesses:
        report_lines.append("#### 📈 Excesses (Over Maximum):")
        report_lines.extend(excesses)
        report_lines.append("")
        
    report_lines.append("#### ✅ On Target:")
    report_lines.extend(perfect)

    # 5. Output and copy
    final_report = "\n".join(report_lines)
    pyperclip.copy(final_report)
    print("Calculations complete! The lack/excess report has been copied to your clipboard.")
    print("\nPreview:\n" + "="*40)
    print(final_report)