import os

import pyperclip


def generate_next_prompt(food_manual_path, daily_need_path, constant_text, check_prompt_text):
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

    parts.append(pyperclip.paste())
        
    if check_prompt_text:
        parts.append(check_prompt_text)

    return "\n\n".join(parts)

if __name__ == "__main__":
    # --- Configuration ---
    food_manual_file = r"DB\food_manual.csv"
    daily_need_file = r"DB\daily_need_table.txt"
    
    # Text to append underneath the food_manual list for the new prompt
    my_next_prompt_text = """Write a text easy to copy in a csv format with two columns: food ID and quantity. For each food item (including prepared meals) on your menu, use the corresponding ID from SR Legacy 2018 (fdc.nal.usda.gov) and food_manual.csv (an extension of the main food database), and enter the quantity as a number where 1 means 100g. Do not include ingredients for prepared meals unless they are also listed as individual items on your menu."""

    check_prompt_text = """Is Gemini's csv output correct?
    """

    # 4. Generate the next prompt and copy to clipboard
    new_prompt = generate_next_prompt(food_manual_file, daily_need_file, my_next_prompt_text, check_prompt_text)
    pyperclip.copy(new_prompt)
    print("The new prompt has been copied to your clipboard.")