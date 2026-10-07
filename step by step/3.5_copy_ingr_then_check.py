from common import (
    DOSE,
    GRAM,
    INGREDIENT_HEADER,
    NEW,
    NEW_FOOD_FILE,
    NONE,
    SEARCH_NOTE,
    answer_note,
    check_food_ids,
    compute_nutrients,
    daily_need_block,
    errors_to_llm,
    food_manual_block,
    get_clipboard,
    ingredient_block,
    load_all_foods,
    load_manual_foods,
    load_new_foods,
    manual_nutrient_food_ids,
    new_food_block,
    normalize,
    parse_answer,
    register_manual_foods,
    save_ingredients,
    save_new_foods,
    set_clipboard,
    to_float,
    to_int,
)

RULES = f"""- quantity: the grams of the ingredient in 100g of the food when the unit of the food is {GRAM}, in one dose of it when its unit is {DOSE}. They do not have to sum to 100: a food loses or absorbs water when it is cooked. For an ingredient of food_manual.csv whose unit is {DOSE}: its number of doses instead of its grams.
- ingredient_description is the exact description of ingredient_fdc_id in its database. When none of the two databases has an ingredient or a close one: {NEW} as ingredient_fdc_id, with your own ingredient_description.
- When the nutrients of a food cannot be deduced from ingredients (a supplement, an isolate, an extract, ...): a single row, with {NONE} as ingredient_fdc_id, and an empty ingredient_description and quantity."""

INTRO = """new_food.csv lists foods that SR Legacy 2018 from fdc.nal.usda.gov does not have: they were added to food_manual.csv, my own foods. The last table gives the ingredients of each of them: the nutrients of daily_need_table.csv are deduced for the food from those of its ingredients.
Every ingredient that brings nutrients must be there, with the right quantity, and ingredient_description, the real description of ingredient_fdc_id, must be the ingredient, or the closest food the databases have. They do not have every cooking method, brand or variant."""

CHECK_PROMPT = f"""{INTRO}
Is it correct?
{SEARCH_NOTE}
{answer_note(INGREDIENT_HEADER)}
{RULES}"""

# Given instead of CHECK_PROMPT when new foods have no ingredient yet
INCOMPLETE_PROMPT = f"""{INTRO}
Some of the ingredients were in none of the two databases: they were added to food_manual.csv and new_food.csv, and need their own ingredients. Those foods of new_food.csv have no row yet in the last table:
{{foods}}
{SEARCH_NOTE}
Write the whole csv again with their rows added, and with the other rows corrected if they are wrong, as a text easy to copy with those columns:
{",".join(f'"{col}"' for col in INGREDIENT_HEADER)}
{RULES}"""


def parse_ingredient_csv(text, new_ids, foods):
    """Strictly validates an ingredient CSV answer and returns its rows as {fdc_id: [[ingredient_fdc_id, description, quantity]]}.

    ingredient_fdc_id is NEW for an ingredient that is in no database. The only row of a food that cannot be made
    from other foods is [NONE, "", ""].
    """
    ingredients, claims = {}, []
    for line, record in parse_answer(text, INGREDIENT_HEADER):
        fdc_id = to_int(record["fdc_id"], f"fdc_id at row {line}")
        if fdc_id not in new_ids:
            raise ValueError(
                f"Unexpected fdc_id {fdc_id} at row {line}: it is not a food of {NEW_FOOD_FILE.name}. "
                f"Expected one of {sorted(new_ids)}."
            )
        rows = ingredients.setdefault(fdc_id, [])
        ingredient_id = record["ingredient_fdc_id"].lower()
        description = record["ingredient_description"]
        if ingredient_id == NONE:
            rows.append([NONE, "", ""])
            continue
        quantity = to_float(record["quantity"], f"quantity at row {line}")
        if quantity <= 0:
            raise ValueError(f"Invalid quantity {quantity} at row {line}.")
        if ingredient_id == NEW:
            if not description:
                raise ValueError(f"The new ingredient at row {line} has no ingredient_description.")
        elif ingredient_id == str(fdc_id):
            raise ValueError(f"The food {fdc_id} is its own ingredient at row {line}.")
        else:
            claims.append((line, ingredient_id, description))
        rows.append([ingredient_id, description, f"{quantity:g}"])

    for fdc_id, rows in ingredients.items():
        if len(rows) > 1 and any(row[0] == NONE for row in rows):
            raise ValueError(f"The food {fdc_id} has {NONE} as ingredient: it cannot have any other row.")
    missing = sorted(new_ids - set(ingredients))
    if missing:
        raise ValueError(f"Those foods of {NEW_FOOD_FILE.name} have no ingredient: {missing}")
    check_food_ids(claims, foods)
    return ingredients


if __name__ == "__main__":
    new_foods = load_new_foods()
    if not new_foods:
        raise ValueError(f"{NEW_FOOD_FILE.name} has no food: run step 3.0 first.")

    # 1. The clipboard holds the ingredient csv answered to the prompt of step 3.0 (or of this step)
    with errors_to_llm(f"{RULES}\n{SEARCH_NOTE}"):
        ingredients = parse_ingredient_csv(get_clipboard(), {fdc_id for fdc_id, _, _ in new_foods}, load_all_foods())

    # 2. The ingredients that are in no database become manual foods, and new foods if they have no nutrient
    wanted = [(row[1], GRAM) for rows in ingredients.values() for row in rows if row[0] == NEW]
    without_ingredient = []
    if wanted:
        ids = register_manual_foods(wanted)
        for rows in ingredients.values():
            for row in rows:
                if row[0] == NEW:
                    row[0] = str(ids[normalize(row[1])])
        added = {ids[normalize(description)] for description, _ in wanted}
        listed = {fdc_id for fdc_id, _, _ in new_foods} | manual_nutrient_food_ids()
        without_ingredient = [food for food in load_manual_foods() if food[0] in added and food[0] not in listed]
        new_foods += without_ingredient
        save_new_foods(new_foods)

    # 3. Save the ingredients, under the real description of their ID, and deduce the nutrients of the foods from them
    foods = load_all_foods()
    save_ingredients([
        [fdc_id, ingredient_id, foods[int(ingredient_id)] if ingredient_id != NONE else "", quantity]
        for fdc_id, rows in ingredients.items() for ingredient_id, _, quantity in rows
    ])
    computed = compute_nutrients(ingredients)
    waiting = [fdc_id for fdc_id, rows in ingredients.items() if rows[0][0] != NONE and fdc_id not in computed]
    if computed:
        print(f"Nutrients deduced for the foods {computed}.")
    if waiting:
        print(f"The foods {waiting} wait for the nutrients of one of their ingredients: step 4.0 deduces theirs.")

    # 4. Ask whether it is right
    prompt = CHECK_PROMPT
    if without_ingredient:
        asked = "\n".join(f"- {fdc_id}: {description}" for fdc_id, description, _ in without_ingredient)
        prompt = INCOMPLETE_PROMPT.format(foods=asked)
        print(f"{len(without_ingredient)} ingredients became new foods: the prompt asks for their ingredients.")
    set_clipboard(
        f"{daily_need_block()}\n\n{food_manual_block()}\n\n{new_food_block(new_foods)}\n\n"
        f"{ingredient_block([fdc_id for fdc_id, _, _ in new_foods], foods)}\n\n{prompt}"
    )
    print("Paste it in a new discussion. If the LLM writes a corrected csv, copy it and run this step again to save it.")
    print("If it says it is correct, go on with 4.0_copy_nutr_if_given_then_check.")
