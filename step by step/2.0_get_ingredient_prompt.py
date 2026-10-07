from common import DOSE, GRAM, set_clipboard

PROMPT = f"""Rewrite the menu above as the list of everything that is eaten or drunk in the day. Write a text easy to copy in a csv format with those columns:
"ingredient_fdc_id","ingredient_description","amount","unit"
- One row per ingredient, never a dish: each ingredient of a dish has its own row. The supplements have their rows too.
- ingredient_description: the ingredient, in the state it is weighed in (raw, cooked, dry, ...).
- amount: the grams of the ingredient eaten in the day, with {GRAM} as unit. Convert the cups, spoons and pieces to grams. Only for a supplement taken as a pill or a capsule: the number of doses, with {DOSE} as unit.
- ingredient_fdc_id: leave it empty. Your memory of the food IDs is not reliable: the foods will be searched in SR Legacy 2018 from your descriptions.
When the menu gives a choice ("soba noodles or brown rice"), keep only one of them."""

if __name__ == "__main__":
    # Starts with blank lines: it is pasted below the menu already put in the field
    set_clipboard(f"\n\n\n{PROMPT}")
