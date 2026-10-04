from common import (
    FOOD_QTT_PROMPT,
    daily_need_block,
    describe_diet,
    file_block,
    food_manual_block,
    get_clipboard,
    load_diet_nutrients,
    load_food_manual,
    parse_diet_csv,
    rows_to_csv,
    set_clipboard,
)

CHECK_PROMPT = """Is Gemini's csv output correct and complete?
The descriptions above are the foods the databases really hold for the IDs of Gemini's csv: an ID is wrong when its description is not the food of the menu.
If Gemini's csv is wrong, write the whole corrected csv."""

ERROR_PROMPT = "Your csv output is incorrect, write the whole corrected csv. The error is:"

if __name__ == "__main__":
    # The clipboard holds the quantity csv answered to the prompt of step 4.0
    food_qtt = get_clipboard().strip()

    # An LLM cannot tell whether an ID is the right one: look the IDs up for it
    try:
        diet = parse_diet_csv(food_qtt)
        resolved = describe_diet(diet)
        # Same verification as step 5.0: every food must have its nutrients in the databases
        load_diet_nutrients(diet)
    except ValueError as e:
        # Give the error back to Gemini instead of asking for a check
        set_clipboard(f"{ERROR_PROMPT}\n{e}\n\n{FOOD_QTT_PROMPT}")
        print("It tells Gemini about the error below: paste it to Gemini instead of the checker.")
        raise

    set_clipboard(
        f"{daily_need_block()}\n\n{food_manual_block(load_food_manual())}\n\n{FOOD_QTT_PROMPT}"
        f"\n\n\nGemini's output:\n{food_qtt}\n\n"
        f"{file_block('Foods found for these IDs', rows_to_csv(['food ID', 'description', 'quantity'], resolved))}\n\n"
        f"{CHECK_PROMPT}"
    )
