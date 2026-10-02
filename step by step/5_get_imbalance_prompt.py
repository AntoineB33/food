import csv
import io
import os
import re
from collections import defaultdict

import pyperclip


def load_daily_needs(filepath):
    """Parses the daily needs CSV to extract Min, Max, and IDs."""
    needs = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row.get('id', '').strip()
            
            # Skip rows where the ID is missing
            if not raw_id:
                continue
                
            # Parse out the integer IDs (handles cases like "629, 621")
            try:
                nutrient_ids = [int(i.strip()) for i in raw_id.split(',')]
            except ValueError:
                print(f"Skipping row with invalid ID format: '{raw_id}'")
                continue
            
            # Extract min/max, handling empty values
            min_str = row.get('min', '').strip()
            max_str = row.get('max', '').strip()
            
            min_val = float(min_str) if min_str else 0.0
            max_val = float(max_str) if max_str else float('inf')
            
            # Since names are not in the CSV, use the ID string as the display name
            clean_name = f"Nutrient {raw_id}"

            needs[clean_name] = {
                "ids": nutrient_ids,
                "min": min_val, 
                "max": max_val, 
                "unit": "" # Units are no longer provided in the CSV
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
    daily_need_file = r"DB\daily_need_table.csv"  # Updated extension
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
        
        min_v = limits['min']
        max_v = limits['max']
        
        max_str = "No limit" if max_v == float('inf') else f"{max_v}"
        record = f"- **{name}**: {total_val:.1f} (Target: {min_v} to {max_str})"
        
        if total_val < min_v:
            lacks.append(record)
        elif total_val > max_v:
            excesses.append(record)
        else:
            perfect.append(record)

    # --- NEW CHECK: Throw an error if there is no lack or excess ---
    if not lacks and not excesses:
        raise ValueError("No nutrition lacks or excesses found. The diet perfectly matches the daily needs!")

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