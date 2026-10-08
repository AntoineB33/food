Some scripts put in the clipboard a prompt to give to an LLM. They are in the `step by step` folder.

`run.bat`, in the root, is the entry point. It starts `0_run_all`, which runs them all in a single terminal: after each script, it says what to paste and copy, waits, then runs the right next script. Typing the number of a script (2.5, ...) jumps to it, c copies the prompt again, q quits. It remembers where the user is: closed and started again, it asks the same question again.

1. `1.0_get_menu_prompt`: gives a prompt to get a vegan menu that satisfies all the daily nutrient needs in the table. The prompt contains the daily nutrient needs table. The script first asks in the terminal the options of the menu, each one answered by y or n: tell the LLM where the user lives, the menu must be as cheap as possible, as environmentally friendly as possible, as quick to prepare as possible, then a free text for anything else. Enter keeps the last answer. The prompt only tells the chosen ones, and so do the prompts that correct the menu (scripts 1.5 and 5). The answers and the address are in DB/menu_options.json, which is not in git: the address is changed there.
1.5. `1.5_copy_menu_then_check`: from the copied menu, the script saves it in menu.csv, then gives a prompt to correct the menu. The prompt contains the daily nutrient needs table and the menu.
2. `2.0_get_food_prompt`: gives a prompt to identify each food of the menu in food.csv from the SR Legacy 2018 from fdc.nal.usda.gov, or in food_manual.csv. The prompt contains the menu and food_manual.csv. The LLM writes one row per food of the menu, with the columns description, fdc_id and fdc_description (the description from USDA, to check if they correspond). A food that is in none of the two csv files has `new` as fdc_id.
2.5. `2.5_copy_foods_then_check`: from the copied food list, the script checks each fdc_description against the csv files, saves the IDs in menu.csv, then gives a prompt to correct the food list. The prompt contains the menu, the food list and food_manual.csv.
3. `3.0_get_ingr_prompt`: adds the foods marked `new` to food_manual.csv, and writes the new food list in new_food.csv: those foods, and every food of food_manual.csv that has no nutrient yet. Gives a prompt to get for each food of the new food list a list of ingredients. The prompt contains food_manual.csv and the new food list. If there is no new food, it says so, and the user goes to script 5.
3.5. `3.5_copy_ingr_then_check`: from the copied ingredient composition table, the script saves it in food_ingredient_manual.csv, then gives a prompt to correct it. If some of the ingredients are also food that are not in both csv files (`new` as ingredient_fdc_id), the script adds them in food_manual.csv and in the new food list, and the prompt asks for their ingredients. A food whose nutrients cannot be deduced from ingredients (a supplement, an isolate, ...) has `none` as only ingredient. The prompt contains the daily nutrient needs table, food_manual.csv, the new food list and the ingredient composition table. For each food in the new food list, the script deduces their nutrient composition from their ingredients, and updates food_nutrient_manual.csv.
4. `4.0_copy_nutr_if_given_then_check`: gives a prompt to correct the new rows in food_nutrient_manual.csv when the nutrient composition of a food can’t simply be the sum on all its ingredients. The prompt contains the daily nutrient needs table, the new food list, their ingredient composition and their nutrient composition. If the clipboard contains a nutrient table, the script first saves its rows in food_nutrient_manual.csv. The script checks if all nutrients from the daily nutrient needs table are present for each new food: the prompt asks for the missing ones.
5. `5.0_get_report`: if the daily nutrient needs table is satisfied by the menu, it says so, and adds the menu to successful_menus.csv. Otherwise, it gives a prompt to correct the menu, and the user must copy the corrected menu and go back to script 1.5. The prompt contains the daily nutrient needs table, the menu, the lack of nutrients and the excess in nutrients.


The name of a script says what the user must copy before running it. The other scripts don’t look at what is in the clipboard.

When the prompt asks the LLM to go check the SR Legacy 2018 DB, it asks it to use its web search tool.

For the scripts 1.5, 2.5, 3.5 and 4., the user must run the script, paste the clipboard into the LLM, and if it says it is correct, go to the next script, otherwise copy the csv table it gives and do this again (run the script, paste, …).

The prompts tell the LLM to either say everything is correct, or write a table in the csv format easy to copy: the whole corrected table, except at script 4., where it only writes the rows to change or to add. The menu, daily nutrient needs table, new food list, etc… are in the csv format.

If the script finds an error, the prompt contains the error message and the user pastes it in the same discussion with the LLM. Otherwise, the given prompt is meant to be the start of a new discussion.

When the menu is corrected at script 5., a food whose description is unchanged keeps its ID: only the other ones are left to identify at script 2.

SR Legacy 2018 has no data for some nutrients (biotin, iodine, chromium, molybdenum, sulfur, and fluoride for most foods). At script 3.5, a nutrient that no ingredient of a food has data for is left out: script 4. asks the LLM for it. At script 5., a nutrient that at least half of the foods of the menu have no data for cannot be judged: it does not count as a lack.


This process allows the user to use its LLM subscription to the fullest instead of paying for API with a fully automatic solution. Here I use Gemini Pro.
