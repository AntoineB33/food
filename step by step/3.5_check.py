from pathlib import Path

import pyperclip


def get_file_content(filepath):
    """Reads and returns the content of a file, or an error message if missing."""
    path = Path(filepath)
    if path.exists():
        try:
            return path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as e:
            return f"[Error reading {filepath}: {e}]"
    else:
        return f"[File not found: {filepath}]"

if __name__ == "__main__":
    # 1. Define the file paths using raw strings to handle backslashes correctly
    files_to_read = [
        r"DB\food_manual.csv",
        r"DB\food_nutrient_manual.csv",
        r"DB\nutrient.csv"
    ]

    # 2. Extract and concatenate the file contents
    combined_text = ""
    for file_path in files_to_read:
        combined_text += f"--- START OF {file_path} ---\n"
        combined_text += get_file_content(file_path)
        combined_text += f"\n--- END OF {file_path} ---\n\n"

    # 3. Define the custom text in the main block
    custom_main_text = r"""
Is the nutrient composition described in DB\food_nutrient_manual.csv correct? 
"""

    # 4. Assemble the final text
    final_output = combined_text + custom_main_text

    # 5. Write to clipboard
    try:
        pyperclip.copy(final_output)
        print("Successfully copied all data to the clipboard!")
    except pyperclip.PyperclipException:
        print("Error: Could not find a copy/paste mechanism for your system.")