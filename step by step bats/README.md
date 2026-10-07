# Step by step

## 1. Menu

1. Run `1.0_get_meal_prompt`.
2. Paste in a new Gemini discussion.
3. Keep the menu Gemini writes.

Purpose: get a vegan menu.

## 2. New foods

1. Run `2.0_get_food_prompt`.
2. Paste in the same discussion.
3. Copy the list of foods.
4. Run `2.5_check`.
5. Put the menu in a new discussion and paste below it.
6. Copy the list, corrected if Gemini corrected it.

Purpose: list the foods of the menu that no database has.

## 3. Ingredients

1. With the list of foods copied, run `2.6_get_ingredient_prompt` and answer `y`.
2. Put the menu in a new discussion and paste below it.
3. Copy the csv.
4. Run `2.7_check_ingr`. Answer `y` if it asks to add ingredients.
5. Put the menu in a new discussion and paste below it.
6. If Gemini writes a csv, copy it and go back to 4. If it says the table is correct, go on.

Purpose: give each new food its ingredients, with the right IDs.

## 4. Nutrients

1. Run `2.9_check_nutr`.
2. Paste in a new discussion and copy the csv.
3. Run `3.0_check_nutr`.
4. If the window of 2.9 said `NOTHING IS SUMMED YET`, go back to 1.
5. Paste in a new discussion.
6. If Gemini writes a csv, copy it and go back to 3. If it says it is correct, go on.
7. Run `3.9_checked`.

Purpose: compute the nutrients of each new food from its ingredients, and have them checked.

## 5. Quantities

1. Run `4.0_get_food_qtt_prompt`.
2. Put the menu in a new discussion and paste below it.
3. Copy the csv.
4. Run `4.5_check`.
5. Paste in a new discussion.
6. Copy the csv, corrected if Gemini corrected it.

Purpose: turn the menu into a list of food IDs and quantities.

## 6. Report

1. With the quantity csv copied, run `5.0_get_imbalance_prompt`.
2. Paste in the discussion of the menu.
3. If Gemini adjusts the menu, start again at chapter 2 with the new menu.

Purpose: compare the menu with the daily needs and fix the lacks and excesses.

## When a step finds an error

1. Leave the window open and read it.
2. Paste in the discussion that gave the csv.
3. Copy the new csv and run the same step again.

Purpose: make Gemini correct a csv the scripts cannot read.
