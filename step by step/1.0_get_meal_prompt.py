from common import daily_need_block, set_clipboard

PROMPT = "Give me a vegan meal plan for a day satisfying the daily needs."

if __name__ == "__main__":
    set_clipboard(f"{daily_need_block()}\n\n{PROMPT}")
