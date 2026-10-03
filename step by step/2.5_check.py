import os

import pyperclip


def copy_csv_format_to_clipboard(file_path, constant_text, prompt):
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        return

    # Extract just the filename from the full path
    file_name = os.path.basename(file_path)

    # Read the CSV content
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            csv_content = file.read()
    except (OSError, UnicodeError) as e:
        print(f"Error reading file: {e}")
        return

    clipboard_content = pyperclip.paste()

    # Construct the final formatted text
    # Using triple backticks and appending the constant text at the bottom
    formatted_text = f"\n\n\nFilename: {file_name}\n```csv\n{csv_content}```\n{constant_text}\n\n\nGemini's output:\n{clipboard_content}\n\n{prompt}"

    # Copy the constructed string to the clipboard
    pyperclip.copy(formatted_text)
    print("Content successfully copied to your clipboard!")

if __name__ == "__main__":
    # --- Configuration ---
    # Replace 'data.csv' with the actual path to your CSV file
    target_file = r"DB\food_manual.csv" 
    
    # Replace this string with the text you want to appear below the CSV
    my_constant_text = """Provide me with a list of all food items (including prepared meals) on your menu that are not listed in the SR Legacy 2018 database (fdc.nal.usda.gov) and food_manual.csv. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu.
The list must be the names of the items, easy to copy."""

    prompt = """Is Gemini's list output correct?
    """

    copy_csv_format_to_clipboard(target_file, my_constant_text, prompt)






