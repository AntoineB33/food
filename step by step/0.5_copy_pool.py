from common import (
    FOOD_LIMIT_FILE,
    FOOD_POOL_FILE,
    GRAM,
    POOL_NOTE,
    add_to_food_pool,
    errors_to_llm,
    get_clipboard,
    load_all_foods,
    load_food_limits,
    load_food_units,
    parse_pool_answer,
    save_food_limits,
    start_food_pool,
)

if __name__ == "__main__":
    pool = start_food_pool()
    foods = load_all_foods()

    # 1. The clipboard holds the answer to the prompt of step 0.0: the foods the LLM proposes for the pool, each one
    # with its ID, which is checked against the databases, and the most of it in a day
    with errors_to_llm(POOL_NOTE):
        most = parse_pool_answer(get_clipboard(), foods)

    # 2. They are in the pool from now on. The max the LLM gives replaces the one of a food the pool already had
    limits = load_food_limits()
    added = add_to_food_pool(most)
    save_food_limits({fdc_id: (limits.get(fdc_id, (None, None))[0], amount) for fdc_id, amount in most.items()})
    units = load_food_units()
    for fdc_id, amount in most.items():
        print(f"{'Added' if fdc_id in added else 'Already there'}: {foods[fdc_id]}, at most {amount:g} {units.get(fdc_id, GRAM)} a day.")
    print(f"The pool has {len(pool) + len(added)} foods, in '{FOOD_POOL_FILE}', their max being in '{FOOD_LIMIT_FILE}'.")
    print("Go on with 0.0_get_menu_from_pool: it computes the menu again.")
