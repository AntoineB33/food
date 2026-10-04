from common import FOOD_LIST_PROMPT, food_manual_block, load_food_manual, set_clipboard, unchecked_foods

if __name__ == "__main__":
    # Only the foods listed after the last checked one
    set_clipboard(f"{food_manual_block(unchecked_foods(load_food_manual()))}\n\n{FOOD_LIST_PROMPT}")
