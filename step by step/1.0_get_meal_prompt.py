import sys

import pyperclip


def prepare_and_copy(file_path: str, prompt: str) -> None:
    """Reads a text file, appends a prompt, and copies it to the clipboard."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        sys.exit(1)
    except (OSError, UnicodeError) as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Combine the file content and the constant prompt
    # Adjust the spacing/newlines between them as needed
    combined_text = f"{file_content}\n\n{prompt}"
    
    try:
        pyperclip.copy(combined_text)
        print("Success: File content and prompt copied to clipboard.")
    except pyperclip.PyperclipException as e:
        print(f"Failed to copy to clipboard. Error: {e}")

if __name__ == "__main__":
    # ---------------------------------------------------------
    # EDIT THESE VARIABLES
    # ---------------------------------------------------------
    FILE_PATH = "DB/daily_need_table.txt"
    CONSTANT_PROMPT = "Give me a vegan meal plan for a day satisfying the daily needs."
    
    prepare_and_copy(FILE_PATH, CONSTANT_PROMPT)
