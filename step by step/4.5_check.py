from common import (
    FOOD_QTT_PROMPT,
    daily_need_block,
    food_manual_block,
    get_clipboard,
    load_food_manual,
    parse_diet_csv,
    set_clipboard,
)

CHECK_PROMPT = "Is Gemini's csv output correct?"

if __name__ == "__main__":
    # The clipboard holds the quantity csv answered to the prompt of step 4.0
    food_qtt = get_clipboard().strip()
    parse_diet_csv(food_qtt)

    set_clipboard(
        f"{daily_need_block()}\n\n{food_manual_block(load_food_manual())}\n\n{FOOD_QTT_PROMPT}"
        f"\n\n\nGemini's output:\n{food_qtt}\n\n{CHECK_PROMPT}"
    )
