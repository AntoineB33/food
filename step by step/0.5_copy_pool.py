from common import (
    FOOD_LIMIT_FILE,
    FOOD_POOL_FILE,
    GRAM,
    MENU_FOOD_FILE,
    MENU_FOOD_NOTE,
    POOL_NOTE,
    add_to_food_pool,
    errors_to_llm,
    get_clipboard,
    load_all_foods,
    load_food_limits,
    load_food_units,
    load_menu_foods,
    parse_pool_answer,
    save_food_limits,
    save_menu_foods,
    start_food_pool,
)

if __name__ == "__main__":
    pool = start_food_pool()
    foods = load_all_foods()

    # 1. The clipboard holds the answer to the prompt of step 0.0: the foods the LLM proposes for the pool, each one
    # with its ID, which is checked against the databases, and the most of it in a day
    # When step 0.0 asked for the foods of a menu that differs from the saved ones, they are the foods of the answer,
    # and so are the ones the LLM adds for this menu later
    chosen = load_menu_foods()
    with errors_to_llm(POOL_NOTE if chosen is None else MENU_FOOD_NOTE):
        most = parse_pool_answer(get_clipboard(), foods)

    # 2. They are in the pool from now on. The max the LLM gives replaces the one of a food the pool already had,
    # except for the foods of such a menu, which may be foods of the pool: those keep theirs
    limits = load_food_limits()
    added = add_to_food_pool(most)
    if chosen is None:
        save_food_limits({fdc_id: (limits.get(fdc_id, (None, None))[0], amount) for fdc_id, amount in most.items()})
    else:
        save_menu_foods(list(dict.fromkeys([*chosen, *most])))
    limits = load_food_limits()
    units = load_food_units()
    for fdc_id in most:
        print(f"{'Added' if fdc_id in added else 'Already there'}: {foods[fdc_id]}, at most {limits[fdc_id][1]:g} {units.get(fdc_id, GRAM)} a day.")
    print(f"The pool has {len(pool) + len(added)} foods, in '{FOOD_POOL_FILE}', their max being in '{FOOD_LIMIT_FILE}'.")
    if chosen is not None:
        print(f"The menu is computed from the {len(load_menu_foods())} foods chosen for it, in '{MENU_FOOD_FILE}'.")
    print("Go on with 0.0_get_menu_from_pool: it computes the menu again.")
