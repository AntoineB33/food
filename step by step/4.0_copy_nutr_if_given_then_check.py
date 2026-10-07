import sys

import pyperclip

from common import (
    NEW_FOOD_FILE,
    NUTRIENT_ANSWER_HEADER,
    NUTRIENT_ID_NOTE,
    NUTRIENT_UNIT_NOTE,
    compute_nutrients,
    daily_need_block,
    errors_to_llm,
    extract_csv,
    ingredient_block,
    load_all_foods,
    load_ingredients,
    load_manual_nutrients,
    load_new_foods,
    load_nutrients,
    needed_nutrient_ids,
    new_food_block,
    nutrient_block,
    parse_answer,
    save_to_nutrient_manual,
    set_clipboard,
    to_float,
    to_int,
)

ANSWER_NOTE = f"""as a text easy to copy in a csv format with those columns:
{",".join(f'"{col}"' for col in NUTRIENT_ANSWER_HEADER)}
{NUTRIENT_UNIT_NOTE}
{NUTRIENT_ID_NOTE}"""

INTRO = """new_food.csv lists foods that SR Legacy 2018 from fdc.nal.usda.gov does not have. The second table gives the ingredients of each of them (quantity: for 100g of the food, or for one dose of it), none meaning that the food cannot be made from other foods. The last table gives their nutrients: the sum of those of their ingredients in SR Legacy 2018, for each nutrient of daily_need_table.csv that at least one ingredient has data for."""

CHECK_PROMPT = f"""{INTRO}
Is this nutrient composition correct? It is not when the nutrients of a food cannot simply be the sum of those of its ingredients: nutrients destroyed by the cooking or lost with the water thrown away, fermentation, an ingredient that is only close to the real one, ...
If it is correct, only answer that it is correct, without any csv. If not, write only the rows to change, {ANSWER_NOTE}"""

MISSING_PROMPT = f"""{INTRO}
Those nutrients of daily_need_table.csv are missing in the last table, the ingredients having no data for them:
{{missing}}
Give a value to each of them, 0 when the food has none. Also correct the other rows when the nutrients of a food cannot simply be the sum of those of its ingredients: nutrients destroyed by the cooking or lost with the water thrown away, fermentation, an ingredient that is only close to the real one, ...
Write the missing rows and the rows to change, {ANSWER_NOTE}"""


def holds_nutrient_csv(text):
    """Tells whether the text holds the nutrient csv of an answer, rather than anything copied before."""
    try:
        return "nutrient_id" in extract_csv(text).split("\n")[0].lower()
    except ValueError:
        return False


def parse_nutrient_csv(text, new_ids):
    """Strictly validates a nutrient CSV answer and returns its rows as (fdc_id, nutrient_id, amount)."""
    needed = set(needed_nutrient_ids())
    rows = {}
    for line, record in parse_answer(text, NUTRIENT_ANSWER_HEADER):
        fdc_id = to_int(record["fdc_id"], f"fdc_id at row {line}")
        nutrient_id = to_int(record["nutrient_id"], f"nutrient_id at row {line}")
        amount = to_float(record["amount"], f"amount at row {line}")
        if amount < 0:
            raise ValueError(f"Negative amount at row {line}.")
        if fdc_id not in new_ids:
            raise ValueError(
                f"Unexpected fdc_id {fdc_id} at row {line}: it is not a food of {NEW_FOOD_FILE.name}. "
                f"Expected one of {sorted(new_ids)}."
            )
        if nutrient_id not in needed:
            raise ValueError(f"Unexpected nutrient_id {nutrient_id} at row {line}: it is not in daily_need_table.csv.")
        if (fdc_id, nutrient_id) in rows:
            raise ValueError(f"Nutrient {nutrient_id} is given twice for the food {fdc_id} (row {line}).")
        rows[fdc_id, nutrient_id] = amount
    return [(fdc_id, nutrient_id, amount) for (fdc_id, nutrient_id), amount in rows.items()]


if __name__ == "__main__":
    new_foods = load_new_foods()
    if not new_foods:
        # Not an error, but exiting this way makes the .bat pause: the message must be read
        sys.exit(f"{NEW_FOOD_FILE.name} has no food: no nutrient to check. Go on with 5.0_get_report.")
    new_ids = [fdc_id for fdc_id, _, _ in new_foods]
    ingredients = load_ingredients()
    without_ingredient = [f"{fdc_id} ({description})" for fdc_id, description, _ in new_foods if fdc_id not in ingredients]
    if without_ingredient:
        raise ValueError(f"Those new foods have no ingredient yet, finish step 3.5 first: {', '.join(without_ingredient)}")

    # 1. When the clipboard holds the nutrient csv answered to the prompt of this step, save its rows
    text = pyperclip.paste().replace("\r\n", "\n")
    if holds_nutrient_csv(text):
        with errors_to_llm(NUTRIENT_ID_NOTE):
            rows = parse_nutrient_csv(text, set(new_ids))
        save_to_nutrient_manual(rows)
    else:
        print("The clipboard holds no nutrient csv: nothing to save.")

    # 2. Deduce the nutrients of the foods that waited for those of an ingredient
    nutrients = load_manual_nutrients()
    computed = compute_nutrients([fdc_id for fdc_id in new_ids if fdc_id not in nutrients])
    if computed:
        print(f"Nutrients deduced for the foods {computed}.")
        nutrients = load_manual_nutrients()

    # 3. Every new food must have every nutrient of daily_need_table.csv. A food that still waits for the
    # nutrients of an ingredient is not asked: it is deduced once the ingredient has them.
    names = load_nutrients()
    missing = []
    for fdc_id, description, _ in new_foods:
        lacking = [n for n in needed_nutrient_ids() if n not in nutrients.get(fdc_id, {})]
        if lacking and (fdc_id in nutrients or not ingredients[fdc_id]):
            missing.append(
                f"- food {fdc_id} ({description}): "
                + ("every nutrient of daily_need_table.csv" if fdc_id not in nutrients
                   else ", ".join(f"{n} ({names[n][0]}, {names[n][1]})" for n in lacking))
            )
    if missing:
        prompt = MISSING_PROMPT.format(missing="\n".join(missing))
        print(f"Nutrients are missing for {len(missing)} of the {len(new_foods)} new foods: the prompt asks for them.")
    else:
        prompt = CHECK_PROMPT
        print("Every new food has every nutrient of the daily need table.")

    set_clipboard(
        f"{daily_need_block()}\n\n{new_food_block(new_foods)}\n\n{ingredient_block(new_ids, load_all_foods())}\n\n"
        f"{nutrient_block(new_ids)}\n\n{prompt}"
    )
    print("Paste it in a new discussion. If the LLM writes a csv, copy it and run this step again to save it.")
    print("If it says it is correct, go on with 5.0_get_report.")
