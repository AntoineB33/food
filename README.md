Some scripts put in the clipboard a prompt to give to an LLM.

1. The script gives a prompt to get a vegan menu that satisfies all the daily nutrient needs in the table. The prompt contains the daily nutrient needs table.
1.5. From the copied menu, the script then gives a prompt to correct the menu. The prompt contains the daily nutrient needs table and the menu.
2. Gives a prompt to get the list of foods involved that are not already in food.csv from the SR Legacy 2018 from fdc.nal.usda.gov, or in food_manual.csv. The prompt contains the menu and food_manual.csv, and asks the LLM to look for the food.csv file on the internet. The prompt would say “Here is my menu and food_manual.csv. Figure out the ingredients, search the USDA SR Legacy database online for each one, and give me the FDC IDs. Write the text in csv format easy to copy with the columns for the food ids and the ingredient ids, and another with the columns ingredient ids and description from USDA (to check if they correspond)”. 
2.5. From the copied new food list, the script gives a prompt to correct it. The prompt contains the menu and the food list.
3. Gives a prompt to get for each food of the new food list a list of ingredients. The prompt contains food_manual.csv and the new food list.
3.5. From the copied ingredient composition table, the script gives a prompt to correct it. If some of the ingredients are also food that are not in both csv files, the script adds them in the new food list. The prompt contains the new food list, the daily nutrient needs table and the ingredient composition table. For each food in the new food list, the script deduces their nutrient composition from their ingredients, and updates food_nutrient_manual.csv.
4. Gives a prompt to correct the new rows in food_nutrient_manual.csv when the nutrient composition of a food can’t simply be the sum on all its ingredients. The prompt contains the new food list, their ingredient composition and their nutrient composition.
5. If the daily nutrient needs table is satisfied by the menu, it says so. Otherwise, it gives a prompt to correct the initial menu, and the user must go back to script 2. The prompt contains the daily nutrient needs table, the menu, the lack of nutrients and the excess in nutrients.


When it doesn’t say “From the copied [...], “, it means that the script doesn’t look at what is in the clipboard.

When the prompt asks the LLM to go check the SR Legacy 2018 DB, it asks it to use its web search tool.

For the scripts 1.5, 2.5, 3.5 and 4., the user must run the script, paste the clipboard into the LLM, and if it says it is correct, go to the next script, otherwise copy the csv table it gives and do this again (run the script, paste, …).

The prompts must tell the LLM to either say everything is correct, or write a table in the csv format easy to copy. The menu, daily nutrient needs table, new food list, etc… are in the csv format.

If the script finds an error, the prompt contains the error message and the user pastes it in the same discussion with the LLM. Otherwise, the given prompt is meant to be the start of a new discussion.
Script 4. must check if all nutrients from the daily nutrient needs table are present for each new food.


This process allows the user to use its LLM subscription to the fullest instead of paying for API with a fully automatic solution. Here I use Gemini Pro.
