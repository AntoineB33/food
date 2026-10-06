from common import FOOD_QTT_PROMPT, daily_need_block, food_manual_block, load_food_manual, set_clipboard

if __name__ == "__main__":
    # The nutrients of the new foods are already saved by steps 2.9 and 3.0
    set_clipboard(f"{daily_need_block()}\n\n{food_manual_block(load_food_manual())}\n\n{FOOD_QTT_PROMPT}")
