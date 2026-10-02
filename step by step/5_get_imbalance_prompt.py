import csv
import io
import os
import re
from collections import defaultdict

import pyperclip


def load_daily_needs(filepath):
    """Parses the daily needs CSV to extract Min, Max, and IDs."""
    needs = {}
    # 'utf-8-sig' ignores hidden Excel BOM characters if present
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row.get('id', '').strip()
            
            if not raw_id:
                continue
                
            try:
                nutrient_ids = [int(i.strip()) for i in raw_id.split(',')]
            except ValueError:
                continue
            
            min_str = row.get('min', '').strip()
            max_str = row.get('max', '').strip()
            
            min_val = float(min_str) if min_str else 0.0
            max_val = float(max_str) if max_str else float('inf')
            
            clean_name = f"Nutrient {raw_id}"

            needs[clean_name] = {
                "ids": nutrient_ids,
                "min": min_val, 
                "max": max_val, 
                "unit": ""
            }
    return needs


def load_nutrient_db(files):
    """Loads nutrient info into a nested dictionary: {fdc_id: {nutrient_id: amount}}"""
    db = defaultdict(lambda: defaultdict(float))
    for file in files:
        if not os.path.exists(file):
            print(f"Warning: {file} not found. Skipping.")
            continue
        
        # 'utf-8-sig' prevents the \ufeff header bug common with Windows CSVs
        with open(file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fdc_id = str(row.get('fdc_id', row.get('id', ''))).strip()
                
                try:
                    # Safely handle empty cells to prevent script crashes
                    nut_str = str(row.get('nutrient_id', '0')).strip()
                    nut_id = int(nut_str) if nut_str else 0
                    
                    amt_str = str(row.get('amount', '0')).strip()
                    amount = float(amt_str) if amt_str else 0.0
                except ValueError:
                    continue
                
                if fdc_id and nut_id:
                    db[fdc_id][nut_id] = amount
    return db


def extract_clipboard_csv(text):
    """Extracts and strictly validates the expected two-column CSV from the clipboard."""
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
        
    if len(rows[0]) != 2:
        raise ValueError(f"CSV Column Mismatch! Expected exactly 2 columns. Found {len(rows[0])}.")
        
    diet = {}
    data_rows_found = 0
    
    for i, row in enumerate(rows):
        if not row:
            continue
            
        if len(row) != 2:
            raise ValueError(f"Malformed CSV format at row {i+1}: expected 2 columns.")
            
        food_id = str(row[0]).strip()
        qty_str = str(row[1]).strip()
        
        try:
            quantity = float(qty_str)
            diet[food_id] = quantity
            data_rows_found += 1
        except ValueError:
            if i == 0:
                continue
            else:
                raise ValueError(f"Invalid quantity '{qty_str}' at row {i+1}.")
                
    if data_rows_found == 0:
        raise ValueError("No valid data rows found in the CSV (only header).")
        
    return diet


if __name__ == "__main__":
    # --- Configuration ---
    daily_need_file = r"DB\daily_need_table.csv"
    nutrient_file = r"DB\food_nutrient.csv"
    manual_nutrient_file = r"DB\food_nutrient_manual.csv"

    # IMPORTANT: If your clipboard quantities are servings (not grams), change this to 1.0!
    PORTION_DIVISOR = 100.0 
    
    clipboard_content = pyperclip.paste()
    diet = extract_clipboard_csv(clipboard_content)
    
    print("Loading databases...")
    daily_needs = load_daily_needs(daily_need_file)
    nutrient_db = load_nutrient_db([nutrient_file, manual_nutrient_file])

    daily_totals = defaultdict(float)
    
    for food_id, quantity in diet.items():
        food_nutrients = nutrient_db.get(food_id, {})
        multiplier = quantity / PORTION_DIVISOR
        
        for nut_id, amount in food_nutrients.items():
            daily_totals[nut_id] += amount * multiplier

    report_lines = ["### Nutrition Gap Report\n"]
    lacks = []
    excesses = []
    perfect = []

    for name, limits in daily_needs.items():
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

    if perfect:
        report_lines.append("#### ✅ On Target:")
        report_lines.extend(perfect)

    final_report = "\n".join(report_lines)
    pyperclip.copy(final_report)
    print("Calculations complete! The lack/excess report has been copied to your clipboard.")
    print("\nPreview:\n" + "="*40)
    print(final_report)