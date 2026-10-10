"""Runs the step by step scripts one after the other in a single terminal (see README.md).

After each script, it says what to do with the LLM, waits, then runs the right next script. It remembers
where the user is: closed and started again, it asks the same question again.
"""
import builtins
import json
import runpy
import sys
from datetime import datetime
from pathlib import Path

import common
import pyperclip
from common import DB_DIR, HISTORY_DIR, AnswerError

FOLDER = Path(__file__).resolve().parent
# The script that was run last, how it ended, the prompt it gave, and the history file of the menu being made
STATE_FILE = DB_DIR / "run_state.json"

# What a script does: PROMPT only gives a prompt, CHECK reads the csv of the clipboard then gives the prompt
# that checks it, and is run again with each corrected csv the LLM writes, SAVE only saves and gives no prompt
PROMPT, CHECK, SAVE = "prompt", "check", "save"
STEPS = [
    ("1.0", "1.0_get_menu_prompt", PROMPT, "the whole answer (the menu as a text, then its csv)"),
    ("1.5", "1.5_copy_menu_then_check", CHECK, "the whole answer (the menu as a text, then its csv)"),
    ("2.0", "2.0_get_food_prompt", PROMPT, "the csv of the foods"),
    ("2.5", "2.5_copy_foods_then_check", CHECK, "the csv of the foods"),
    ("3.0", "3.0_get_ingr_prompt", PROMPT, "the csv of the ingredients"),
    ("3.5", "3.5_copy_ingr_then_check", CHECK, "the csv of the ingredients"),
    ("4.0", "4.0_copy_nutr_if_given_then_check", CHECK, "the csv of the nutrients"),
    ("5.0", "5.0_get_product_prompt", PROMPT, "the whole answer (the csv of the products, then the csv of their nutrients)"),
    ("5.5", "5.5_copy_products", SAVE, "the whole answer (the csv of the products, then the csv of their nutrients)"),
    ("6.0", "6.0_get_report", PROMPT, "the whole answer (the corrected menu as a text, then its csv)"),
    ("6.5", "6.5_copy_limits", SAVE, "the whole answer (the csv of the limits of the foods)"),
]
NUMBERS = [number for number, _, _, _ in STEPS]
# The products of the foods of the menu are asked, then saved, before the report
PRODUCT_PROMPT, PRODUCTS, REPORT = NUMBERS.index("5.0"), NUMBERS.index("5.5"), NUMBERS.index("6.0")
NEW_FOODS = NUMBERS.index("3.0")
# The limits of the foods whose computed amount the LLM refuses are saved, then the report is run again
LIMITS = NUMBERS.index("6.5")
# Where the corrected menu of the report goes
AFTER_REPORT = NUMBERS.index("1.5")

# How a script ended: its prompt is in the clipboard, the prompt that tells the LLM about the error of its csv is,
# the script says there is nothing to ask the LLM and that the next part is next, or it failed for another reason
OK, ANSWER_ERROR, NOTHING_TO_DO, ERROR = "ok", "answer error", "nothing to do", "error"
# The menu satisfies the daily needs: the prompt that asks for its risks and problems is in the clipboard
REVIEW = "review"


def symbol(sign, text):
    """Returns a sign and what it means, the text alone in a terminal that cannot show the sign."""
    try:
        sign.encode(sys.stdout.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        return text
    return f"{sign} {text}"


# What to do with the LLM, said in a few signs before each question: where to paste the prompt, what to copy from
# the answer, and what to type then. ? gives the whole sentence
NEW_CHAT, SAME_CHAT = symbol("\U0001F195", "NEW chat"), symbol("\U0001F501", "SAME chat")
WHOLE, CSV_ONLY = symbol("\U0001F4C4", "copy WHOLE answer"), symbol("\U0001F4CA", "copy CSV only")
CORRECT, FINISHED, FIX = symbol("\u2705", "LLM says correct:"), symbol("\U0001F3C1", "finished:"), symbol("\u26A0", "fix it")
ENTER = symbol("\u23CE", "Enter")


def load_state():
    """Returns (step, how it ended, prompt) of the script that was run last, or None."""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return NUMBERS.index(state["step"]), state["result"], state["prompt"]
    except (OSError, ValueError, KeyError):
        return None


def save_state(current, result, prompt):
    history = Path(common.history_file).name if common.history_file else None
    STATE_FILE.write_text(
        json.dumps({"step": NUMBERS[current], "result": result, "prompt": prompt, "history": history}),
        encoding="utf-8",
    )


class History:
    """A stream of the terminal that also writes what is printed to the history of the menu being made."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        common.write_history(text)
        return self.stream.write(text)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def keep_history():
    """Makes all that is printed and typed from now on go to the history too, and goes on with the history file of
    the menu that was being made, when there is one."""
    try:
        name = json.loads(STATE_FILE.read_text(encoding="utf-8"))["history"]
        if name and (HISTORY_DIR / name).exists():
            common.history_file = HISTORY_DIR / name
    except (OSError, ValueError, KeyError):
        pass
    sys.stdout, sys.stderr = History(sys.stdout), History(sys.stderr)
    typed = builtins.input

    def logged_input(question=""):
        # The terminal shows the question and what is typed without printing them
        file, common.history_file = common.history_file, None
        try:
            answer = typed(question)
        finally:
            common.history_file = file
        common.write_history(f"{question}{answer}\n")
        return answer

    builtins.input = logged_input
    common.write_history(f"\n{'-' * 20} {datetime.now():%Y-%m-%d %H:%M:%S}: run.bat is started again {'-' * 20}\n")


def new_history():
    """Starts the history file of a new menu, named after the date and the time."""
    now = datetime.now()
    HISTORY_DIR.mkdir(exist_ok=True)
    if common.history_file:
        print(f"The history of the menu before is in '{common.history_file}'.")
    common.history_file = HISTORY_DIR / f"{now:%Y-%m-%d %Hh%Mm%S}.txt"
    common.write_history(f"History of the menu started on {now:%Y-%m-%d} at {now:%H:%M:%S}\n")
    print(f"The history of this menu is kept in '{common.history_file}'.")


def holds_prompt(prompt):
    """Whether the clipboard still holds the prompt, whatever its blanks and line ends became."""
    return prompt is not None and pyperclip.paste().split() == prompt.split()


def tell_clipboard(prompt):
    """Says whether the clipboard holds the prompt, for the user who forgot what was copied last."""
    text = pyperclip.paste().strip()
    if prompt is None:
        print("This step gave no prompt.")
    elif holds_prompt(prompt):
        print("The clipboard holds the prompt: nothing was copied since. Paste it to the LLM if you did not yet.")
    elif not text:
        print("The clipboard is empty or holds no text: type c to copy the prompt again.")
    else:
        start = " ".join(text.split())
        print(
            f"The clipboard does not hold the prompt, but a text of {len(text)} characters that may be the answer "
            f"of the LLM. It starts with:\n    {start[:150]}{'...' if len(start) > 150 else ''}"
        )


def ask(question, prompt=None, answers=(), signs=()):
    """Asks until the answer is one of the answers, the number of a step to jump to, or q to quit.

    signs say the question in a few words, which are shown instead of it: ? then shows the question itself.
    c copies the prompt again and w tells what the clipboard holds, instead of answering. Returns the answer in
    lower case, empty for Enter.
    """
    while True:
        answer = input(
            f"\n>>> {'   |   '.join(signs) or question}\n    ({'? explains, ' if signs else ''}c copies the prompt again, "
            "w tells what the clipboard holds, a step number jumps to it, q quits): "
        ).strip().lower()
        if answer == "q":
            sys.exit()
        if answer == "?" and signs:
            print(question)
        elif answer == "w":
            tell_clipboard(prompt)
        elif answer == "c":
            if prompt is None:
                print("This step gave no prompt.")
            else:
                pyperclip.copy(prompt)
                print("The prompt has been copied to your clipboard again.")
        elif not answer or answer in NUMBERS or answer in answers:
            return answer
        else:
            print(f"'{answer}' is not understood. The steps are: {', '.join(NUMBERS)}.")


def run(name):
    """Runs a script, and returns how it ended and the prompt it gave, None without any."""
    print(f"\n{'=' * 20} {name} {'=' * 20}")
    common.last_prompt = None
    common.last_prompt_is_review = False
    try:
        runpy.run_path(str(FOLDER / f"{name}.py"), run_name="__main__")
        result = REVIEW if common.last_prompt_is_review else OK
    except AnswerError as e:
        print(f"\nError in the csv of the clipboard:\n{e}")
        result = ANSWER_ERROR
    except ValueError as e:
        print(f"\nError: {e}")
        result = ERROR
    except SystemExit as e:
        # The way a script says there is nothing to ask the LLM
        print(f"\n{e.code}")
        result = NOTHING_TO_DO
    return result, common.last_prompt


def ask_what_next(current, result, prompt):
    """Says what to do with the LLM after a script, waits, and returns the script to run then."""
    number, _, kind, copied = STEPS[current]
    following = current + 1
    what = WHOLE if copied.startswith("the whole answer") else CSV_ONLY
    if result == ANSWER_ERROR:
        following = current
        answer = ask(
            f"Paste the prompt in the discussion that gave the csv, copy {copied} the LLM writes again, "
            f"then press Enter to run {number} again",
            prompt,
            signs=(SAME_CHAT, what, f"{ENTER} runs {number} again"),
        )
    elif result == ERROR:
        following = current
        answer = ask(f"Fix it, then press Enter to run {number} again", prompt, signs=(FIX, f"{ENTER} runs {number} again"))
    elif result == NOTHING_TO_DO:
        # No food to identify: the new foods are next. No new food: the products are. No food without product, or
        # a menu whose text alone was written again: the report is
        following = {AFTER_REPORT: REPORT, NUMBERS.index("2.0"): NEW_FOODS, PRODUCT_PROMPT: REPORT}.get(current, PRODUCT_PROMPT)
        answer = ask(f"Press Enter to run {NUMBERS[following]}", prompt, signs=(f"{ENTER} runs {NUMBERS[following]}",))
    elif current == PRODUCT_PROMPT:
        answer = ask(
            f"Paste the prompt in a new discussion, copy {copied} the LLM writes, then press Enter to run "
            f"{NUMBERS[following]}. The report does not need the products: type {NUMBERS[REPORT]} to go on without them",
            prompt,
            signs=(NEW_CHAT, what, f"{ENTER} runs {NUMBERS[following]}", f"{NUMBERS[REPORT]} goes on without products"),
        )
    elif current == PRODUCTS:
        following = REPORT
        answer = ask(
            f"Press Enter to run {NUMBERS[following]}, or type {NUMBERS[PRODUCT_PROMPT]} to ask for the foods that "
            "still have no product",
            signs=(f"{ENTER} runs {NUMBERS[following]}", f"{NUMBERS[PRODUCT_PROMPT]} asks the products still missing"),
        )
    elif current == LIMITS:
        following = REPORT
        answer = ask(f"Press Enter to run {NUMBERS[following]}", signs=(f"{ENTER} runs {NUMBERS[following]}",))
    elif result == REVIEW:
        following = AFTER_REPORT
        while True:
            answer = ask(
                "The menu satisfies the daily needs. Paste the prompt in a new discussion: it asks for its risks and "
                "problems. If the LLM writes a corrected menu, copy its whole answer, then press Enter to run "
                f"{NUMBERS[following]}. If it finds none, it is finished: q to quit, or type {NUMBERS[0]} to start a new menu",
                prompt,
                signs=(
                    NEW_CHAT, f"corrected menu: {what}, {ENTER} runs {NUMBERS[following]}",
                    f"{FINISHED} no problem found, q quits, {NUMBERS[0]} starts a new menu",
                ),
            )
            # Enter with the prompt still in the clipboard would give the script its own prompt to read
            if answer or not holds_prompt(prompt):
                break
            print("The clipboard still holds the prompt: copy the answer of the LLM first, or type q if it finds no problem.")
    elif current == REPORT and prompt is None:
        # The state of a report that was run before it gave a prompt for a menu that satisfies the daily needs
        following = 0
        answer = ask(
            f"It is finished: q to quit, or press Enter to start a new menu at {NUMBERS[following]}",
            signs=(f"{FINISHED} q quits", f"{ENTER} starts a new menu at {NUMBERS[following]}"),
        )
    elif current == REPORT:
        # The LLM corrects the products or the menu, or gives limits to the amounts that were computed: what its
        # answer holds tells which script reads it
        while True:
            answer = ask(
                f"Paste the prompt in a new discussion, copy the whole answer of the LLM, then press Enter: it runs "
                f"{NUMBERS[PRODUCTS]} when the LLM corrected products, {NUMBERS[AFTER_REPORT]} when it wrote the menu, "
                f"{NUMBERS[LIMITS]} when it wrote limits of foods",
                prompt,
                signs=(
                    NEW_CHAT, what,
                    f"{ENTER} runs {NUMBERS[AFTER_REPORT]} (menu), {NUMBERS[PRODUCTS]} (products) or {NUMBERS[LIMITS]} (limits)",
                ),
            )
            answered = None if holds_prompt(prompt) else common.answer_kind(pyperclip.paste())
            if answer or answered:
                break
            print("The clipboard holds no csv of a menu, of products nor of limits: copy the whole answer of the LLM first.")
        following = {common.MENU_ANSWER: AFTER_REPORT, common.LIMIT_ANSWER: LIMITS}.get(answered, PRODUCTS)
    elif kind == CHECK:
        while True:
            answer = ask(
                f"Paste the prompt in a new discussion. If the LLM writes a csv, copy {copied}, then press Enter to run "
                f"{number} again. If it says it is correct, type y to go on with {NUMBERS[following]}",
                prompt,
                answers=("y",),
                signs=(
                    NEW_CHAT, f"corrected: {what}, {ENTER} runs {number} again",
                    f"{CORRECT} y goes on with {NUMBERS[following]}",
                ),
            )
            # Enter with the prompt still in the clipboard would give the script its own prompt to read
            if answer or not holds_prompt(prompt):
                break
            print("The clipboard still holds the prompt: copy the answer of the LLM first, or type y if it says it is correct.")
        if not answer:
            following = current
    else:
        answer = ask(
            f"Paste the prompt in a new discussion, copy {copied} the LLM writes, "
            f"then press Enter to run {NUMBERS[following]}",
            prompt,
            signs=(NEW_CHAT, what, f"{ENTER} runs {NUMBERS[following]}"),
        )
    return NUMBERS.index(answer) if answer in NUMBERS else following


if __name__ == "__main__":
    keep_history()
    print("Steps:" + "".join(f"\n  {number}  {name}" for number, name, _, _ in STEPS))
    state = load_state()
    if state:
        # The script is not run again: its prompt may already be in a discussion
        print(f"\nYou were at step {NUMBERS[state[0]]}, which was already run. Type 1.0 to start again from the beginning.")
        current = ask_what_next(*state)
    else:
        answer = ask("Press Enter to start at 1.0")
        current = NUMBERS.index(answer) if answer else 0

    while True:
        # A menu starts at the first step, or at the step the user jumps to when no history is kept yet
        if current == 0 or not common.history_file:
            new_history()
        state = run(STEPS[current][1])
        save_state(current, *state)
        current = ask_what_next(current, *state)
