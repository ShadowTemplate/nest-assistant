"""TEAM 3 — does the assistant refuse near-miss questions, and only those?

    uv run python tools/refusal_traps.py

Runs ``eval/refusal_traps.yaml`` through the real pipeline with EVAL's own
scorer, then prints every question with what the assistant did. Calls the model
once per question (~13 calls): this is a measurement, not a test, so it is not
part of ``make check``.

Exits 1 if any trap was answered or any control was refused.
"""

from __future__ import annotations

import sys

from nest_assistant import evaluate, llm
from nest_assistant.config import EVAL_DIR
from nest_assistant.pipeline import Pipeline

TRAPS = EVAL_DIR / "refusal_traps.yaml"


def main() -> int:
    if not llm.available():
        print("No ANTHROPIC_API_KEY: without a model every answer is a refusal.")
        return 2
    questions = evaluate.load_questions(TRAPS)
    if not questions:
        print(f"No questions loaded from {TRAPS} (they only run on the real data/ corpus).")
        return 2

    scorecard = evaluate.run(Pipeline(), questions)
    wrong = 0
    for item in scorecard.details:
        ok = item["refused"] == (item["expected"] == "refusal")
        wrong += not ok
        print(
            f"{'OK' if ok else 'XX'}  {item['id']}  expected={item['expected']:<7}  "
            f"refused={item['refused']!s:<5}  {item['question']}"
        )
        if not item["refused"]:
            print(f"      {item['answer'][:160]}")
    print()
    print(scorecard.summary())
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
