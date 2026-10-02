import csv
from collections import deque
from pathlib import Path

# Define paths using pathlib to automatically handle Windows backslashes
csv_file = Path("DB/food_manual.csv")
output_file = Path("step by step bats/last_checked_food.txt")

# Ensure the output directory exists before attempting to write
output_file.parent.mkdir(parents=True, exist_ok=True)

try:
    with open(csv_file, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        # deque with maxlen=1 is an extremely memory-efficient way to get the last row of a large file
        last_row_queue = deque(reader, maxlen=1)
        
        if last_row_queue:
            last_row = last_row_queue[0]
            
            if 'description' in last_row:
                # Write the extracted description to the text file
                output_file.write_text(last_row['description'], encoding='utf-8')
                print(f"Successfully wrote description to {output_file}")
            else:
                print("Error: The column 'description' was not found in the CSV headers.")
        else:
            print("Error: The CSV file contains no data rows.")

except FileNotFoundError:
    print(f"Error: The input file '{csv_file}' does not exist.")
except (OSError, UnicodeError, csv.Error) as e:
    print(f"An unexpected error occurred: {e}")