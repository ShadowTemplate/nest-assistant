"""TEAM 5 — EVAL · *how do we know it works?*

You own::

    evaluate.run(pipeline) -> Scorecard

Your tasks
----------
W1-5.1  The question set      -> ``eval/questions.yaml``. The most valuable
                                 artefact produced on the day.
W1-5.2  Evaluation harness    -> this file, for real
W1-5.3  Red team + guardrails -> ``eval/redteam.yaml`` + ``guardrails.py``.
                                 **Not droppable.**

Why this team matters more than it looks
----------------------------------------
Everyone else can tell whether their thing runs. Only you can tell whether it
*works*. In March 2027 the only reason anyone will be able to say "we got
better" is that you produced a number in October that they can beat.

The number to protect
---------------------
``tier_leaks`` must be **zero**. Every other metric is a trade-off; this one is
not. A scorecard with a non-zero leak count and a great correctness score
describes a system we cannot deploy.

**It will not be zero at 10:30.** INDEX's stub does not filter by tier, on
purpose (see ``index/__init__.py``). Report it red, loudly, on the board. When
team 2 finishes W1-2.2 it goes green in front of everyone, which is the single
most satisfying thing that happens all day.

Stuck for 15 minutes?
---------------------
Run ``make eval``. It works right now against the stub pipeline. Read the
numbers it produces and ask yourself which of them you would be embarrassed to
defend — that is your task list.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..config import BUILD_DIR, DATA_DIR, EVAL_DIR, RESULTS_DIR, corpus_dir
from ..schema import PipelineProtocol, Scorecard, tier_allows

OWNER = "TEAM 5 — EVAL"
INTERFACE = "evaluate.run(pipeline) -> Scorecard"
STATUS = "stub"  # flip to "real" when you replace run() below. `make board` reads this.

QUESTIONS_PATH = EVAL_DIR / "questions.yaml"
REDTEAM_PATH = EVAL_DIR / "redteam.yaml"
FULL_RESULTS_DIR = BUILD_DIR / "eval-results"
"""Unredacted scorecards, answer text included. Gitignored (under ``build/``):
for debugging on the laptop that produced them, never for committing."""


def load_questions(path: Path | None = None, corpus: str | None = None) -> list[dict[str, Any]]:
    """Read ``eval/questions.yaml``.

    Each entry::

        id: q001
        question: "Quanto costa una camera singola?"
        tier: public                  # who is asking
        expect: answer                # "answer" or "refusal"
        expected_sources: [prezzi-2026.md]
        expected_answer: "10.450"     # or the key facts it must contain
        corpus: data                  # optional: only valid on data/ or fixtures/
        source: document              # where the question came from — see below
        notes: "..."

    Questions tagged with a ``corpus`` that is not the one in use are skipped,
    so the same file scores honestly on a fresh clone (fixtures/) and on the
    real documents (data/). Pass ``corpus="all"`` to get every question.

    ``source`` is not bureaucracy. A question set written by residents
    over-represents what residents care about. Recording where each question
    came from is what lets you say so honestly in ``eval/README.md``.
    """
    path = path or QUESTIONS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    items = list(raw) if isinstance(raw, list) else list(raw.get("questions", []))
    if corpus is None:
        corpus = "data" if corpus_dir() == DATA_DIR else "fixtures"
    if corpus == "all":
        return items
    return [q for q in items if q.get("corpus", corpus) == corpus]


# ---------------------------------------------------------------------------
# TEAM 5 — REPLACE ME (W1-5.2)
# ---------------------------------------------------------------------------
def run(pipeline: PipelineProtocol, questions: list[dict[str, Any]] | None = None) -> Scorecard:
    """Score ``pipeline`` against the question set and return a Scorecard.

    Contract you must satisfy:

    * Runs against **any** object with ``.ask()`` and ``.retrieve()`` — the real
      pipeline, a stub, next year's self-hosted one. Never import
      ``index``/``answer`` directly here, or you cannot compare two systems.
    * ``tier_leaks`` counts chunks returned *above* the asking tier, measured on
      the **raw retrieval**, before any downstream filtering. Measure the disease,
      not the bandage.
    * Metrics that cannot be gamed. A system that refuses everything must score
      badly, and so must one that answers everything. Check both directions.
    * Deterministic enough to compare October with March. Write the model name
      and the date into the results file.

    What the baseline below actually does — and where it is weak:

    * **Retrieval hit rate** — did any retrieved chunk come from an expected
      source? Fair. Keep it.
    * **Correctness** — naive substring match against ``expected_answer``. This
      is *bad*: it fails a correct answer that is worded differently. **Replacing
      this with an LLM-as-judge is task W1-5.2.** When you do, remember that a
      model grading a model is both useful and suspect: spot-check its verdicts
      by hand and write down how often it was wrong.
    * **Refusal precision/recall** — real, and worth keeping as is.

    Args:
        pipeline: the thing under test.
        questions: defaults to ``eval/questions.yaml``.
    """
    questions = questions if questions is not None else load_questions()
    if not questions:
        return Scorecard(notes="no questions in eval/questions.yaml — that is task W1-5.1")

    details: list[dict[str, Any]] = []
    retrieval_hits = 0
    retrieval_scored = 0
    correct = 0
    answerable = 0
    should_refuse = 0
    did_refuse = 0
    refused_correctly = 0
    tier_leaks = 0

    for item in questions:
        question = item.get("question", "")
        tier = item.get("tier", "public")
        expects_refusal = item.get("expect", "answer") == "refusal"

        try:
            retrieved = pipeline.retrieve(question, tier)
        except Exception:  # noqa: BLE001 - a broken retriever is a result, not a crash
            retrieved = []

        leaked = [c.id for c in retrieved if not tier_allows(tier, c.tier)]
        tier_leaks += len(leaked)

        expected_sources = item.get("expected_sources") or []
        if expected_sources:
            retrieval_scored += 1
            if any(c.source in expected_sources for c in retrieved):
                retrieval_hits += 1

        answer = pipeline.ask(question, tier)

        if expects_refusal:
            should_refuse += 1
            if answer.refused:
                refused_correctly += 1
        else:
            answerable += 1
            expected = str(item.get("expected_answer", "")).lower()
            # TEAM 5: this is the weak line. An LLM judge goes here.
            if not answer.refused and expected and expected in answer.text.lower():
                correct += 1

        if answer.refused:
            did_refuse += 1

        details.append(
            {
                "id": item.get("id"),
                "question": question,
                "tier": tier,
                "expected": "refusal" if expects_refusal else "answer",
                "refused": answer.refused,
                "citations": answer.citations,
                "leaked_chunks": leaked,
                "answer": answer.text[:300],
            }
        )

    return Scorecard(
        n_questions=len(questions),
        retrieval_hit_rate=(retrieval_hits / retrieval_scored) if retrieval_scored else 0.0,
        answer_correctness=(correct / answerable) if answerable else 0.0,
        refusal_precision=(refused_correctly / did_refuse) if did_refuse else 0.0,
        refusal_recall=(refused_correctly / should_refuse) if should_refuse else 0.0,
        tier_leaks=tier_leaks,
        notes="baseline harness — correctness is substring matching (TEAM 5: W1-5.2)",
        details=details,
    )


def redact(scorecard: Scorecard) -> dict[str, Any]:
    """The scorecard as it may be committed: answer text only for ``public`` questions.

    An answer to a resident or staff question quotes resident or staff documents —
    the residents' guide holds the wifi password, the room list holds names. The
    repository is public, so those answers keep everything except their text:
    the score, whether it refused, which chunk ids it cited, what leaked.
    """
    card = scorecard.to_dict()
    for row in card["details"]:
        tier = row.get("tier", "public")
        if tier != "public" and "answer" in row:
            row["answer"] = f"(withheld: {tier} tier)"
    return card


def save(scorecard: Scorecard, label: str = "") -> Path:
    """Write a dated scorecard to ``eval/results/``, and a full copy to ``build/``.

    March compares itself against October by reading ``eval/results/``. Commit
    those files: they hold questions and scores, and answer text only for
    ``public`` questions (see :func:`redact`). The full copy, every answer
    included, goes to :data:`FULL_RESULTS_DIR` — gitignored, for debugging here.

    Returns the path of the committable file.
    """
    stamp = date.today().isoformat()
    name = f"scorecard-{stamp}{'-' + label if label else ''}.json"

    FULL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    full = json.dumps(scorecard.to_dict(), indent=2, ensure_ascii=False)
    (FULL_RESULTS_DIR / name).write_text(full, encoding="utf-8")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps(redact(scorecard), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


__all__ = [
    "run",
    "load_questions",
    "save",
    "redact",
    "FULL_RESULTS_DIR",
    "QUESTIONS_PATH",
    "REDTEAM_PATH",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
