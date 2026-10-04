from common import (
    FOOD_LIST_PROMPT,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    set_clipboard,
    unchecked_foods,
)

CHECK_PROMPT = "Is Gemini's list output correct and complete?"

if __name__ == "__main__":
    # The clipboard holds the food list answered to the prompt of step 2.0
    food_list = get_clipboard().strip()

    # Same part of food_manual.csv as step 2.0: the foods listed after the last checked one
    foods = unchecked_foods(load_food_manual())

    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(
        f"\n\n\n{food_manual_block(foods)}\n\n{FOOD_LIST_PROMPT}"
        f"\n\n\nGemini's output:\n{food_list}\n\n{CHECK_PROMPT}"
    )
