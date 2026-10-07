# Step by step

## 1. Menu

1. Run `1.0_get_meal_prompt`.
2. Paste in a new Gemini discussion.
3. Keep the menu Gemini writes.

Purpose: get a vegan menu.

## 2. Ingredients

1. Run `2.0_get_ingredient_prompt`.
2. Put the menu in a new discussion and paste below it.
3. Copy the csv.
4. Run `2.5_check_ingr`. Answer `y` if it asks to add ingredients.
5. Put the menu in a new discussion and paste below it.
6. If Gemini writes a csv, copy it and go back to 4. If it says the table is correct, go on.

Purpose: turn the menu into a list of foods of the databases, each with its amount for the day.

## 3. Nutrients of the new foods

1. Run `3.0_get_nutr_prompt`. If the window says there is nothing to ask, go to chapter 4.
2. Paste in a new discussion and copy the csv.
3. Run `3.5_check_nutr`.
4. Paste in a new discussion.
5. If Gemini writes a csv, copy it and go back to 3. If it says it is correct, go on.

Purpose: get the nutrients of the ingredients that no database has.

## 4. Report

1. Run `4.0_get_report`.
2. Paste in the discussion of the menu.
3. If Gemini adjusts the menu, start again at chapter 2 with the new menu.

Purpose: compare the menu with the daily needs and fix the lacks and excesses.

## When a step finds an error

1. Leave the window open and read it.
2. Paste in the discussion that gave the csv.
3. Copy the new csv and run the same step again.

Purpose: make Gemini correct a csv the scripts cannot read.
