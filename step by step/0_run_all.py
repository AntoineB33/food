"""Runs the step by step scripts one after the other in a single terminal (see README.md).

After each script, it says what to do with the LLM, waits, then runs the right next script. It remembers
where the user is: closed and started again, it asks the same question again.
"""
import json
import runpy
import sys
from pathlib import Path

import common
import pyperclip
from common import DB_DIR, AnswerError

FOLDER = Path(__file__).resolve().parent
# The script that was run last, how it ended and the prompt it gave
STATE_FILE = DB_DIR / "run_state.json"

# What a script does: PROMPT only gives a prompt, CHECK reads the csv of the clipboard then gives the prompt
# that checks it, and is run again with each corrected csv the LLM writes
PROMPT, CHECK = "prompt", "check"
STEPS = [
    ("1.0", "1.0_get_menu_prompt", PROMPT, "the whole answer (the menu as a text, then its csv)"),
    ("1.5", "1.5_copy_menu_then_check", CHECK, "the whole answer (the menu as a text, then its csv)"),
    ("2.0", "2.0_get_food_prompt", PROMPT, "the csv of the foods"),
    ("2.5", "2.5_copy_foods_then_check", CHECK, "the csv of the foods"),
    ("3.0", "3.0_get_ingr_prompt", PROMPT, "the csv of the ingredients"),
    ("3.5", "3.5_copy_ingr_then_check", CHECK, "the csv of the ingredients"),
    ("4.0", "4.0_copy_nutr_if_given_then_check", CHECK, "the csv of the nutrients"),
    ("5.0", "5.0_get_report", PROMPT, "the whole answer (the corrected menu as a text, then its csv)"),
]
NUMBERS = [number for number, _, _, _ in STEPS]
REPORT = NUMBERS.index("5.0")
# Where the corrected menu of the report goes
AFTER_REPORT = NUMBERS.index("1.5")

# How a script ended: its prompt is in the clipboard, the prompt that tells the LLM about the error of its csv is,
# the script says there is nothing to ask the LLM and that the report is next, or it failed for another reason
OK, ANSWER_ERROR, NOTHING_TO_DO, ERROR = "ok", "answer error", "nothing to do", "error"


def load_state():
    """Returns (step, how it ended, prompt) of the script that was run last, or None."""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return NUMBERS.index(state["step"]), state["result"], state["prompt"]
    except (OSError, ValueError, KeyError):
        return None


def save_state(current, result, prompt):
    STATE_FILE.write_text(
        json.dumps({"step": NUMBERS[current], "result": result, "prompt": prompt}), encoding="utf-8"
    )


def ask(question, prompt=None, answers=()):
    """Asks until the answer is one of the answers, the number of a step to jump to, or q to quit.

    c copies the prompt again instead of answering. Returns the answer in lower case, empty for Enter.
    """
    while True:
        answer = input(
            f"\n>>> {question}\n    (c to copy the prompt again, the number of a step to jump to it, q to quit): "
        ).strip().lower()
        if answer == "q":
            sys.exit()
        if answer == "c":
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
    try:
        runpy.run_path(str(FOLDER / f"{name}.py"), run_name="__main__")
        result = OK
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
    if result == ANSWER_ERROR:
        following = current
        answer = ask(
            f"Paste the prompt in the discussion that gave the csv, copy {copied} the LLM writes again, "
            f"then press Enter to run {number} again",
            prompt,
        )
    elif result == ERROR:
        following = current
        answer = ask(f"Fix it, then press Enter to run {number} again", prompt)
    elif result == NOTHING_TO_DO:
        following = REPORT
        answer = ask(f"Press Enter to run {NUMBERS[following]}", prompt)
    elif current == REPORT and prompt is None:
        # The report gives no prompt when the menu satisfies the daily needs
        following = 0
        answer = ask(f"It is finished: q to quit, or press Enter to start a new menu at {NUMBERS[following]}")
    elif current == REPORT:
        following = AFTER_REPORT
        answer = ask(
            f"Paste the prompt in a new discussion, copy {copied} the LLM writes, "
            f"then press Enter to run {NUMBERS[following]}",
            prompt,
        )
    elif kind == CHECK:
        while True:
            answer = ask(
                f"Paste the prompt in a new discussion. If the LLM writes a csv, copy {copied}, then press Enter to run "
                f"{number} again. If it says it is correct, type y to go on with {NUMBERS[following]}",
                prompt,
                answers=("y",),
            )
            # Enter with the prompt still in the clipboard would give the script its own prompt to read
            if answer or pyperclip.paste().split() != (prompt or "").split():
                break
            print("The clipboard still holds the prompt: copy the answer of the LLM first, or type y if it says it is correct.")
        if not answer:
            following = current
    else:
        answer = ask(
            f"Paste the prompt in a new discussion, copy {copied} the LLM writes, "
            f"then press Enter to run {NUMBERS[following]}",
            prompt,
        )
    return NUMBERS.index(answer) if answer in NUMBERS else following


if __name__ == "__main__":
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
        result, prompt = run(STEPS[current][1])
        save_state(current, result, prompt)
        current = ask_what_next(current, result, prompt)
