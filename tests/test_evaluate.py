"""TEAM 5 — EVAL: the harness must not be gameable, and must count leaks.

These tests use fake pipelines, so they run offline with no key. They check the
scorer itself: a system that answers everything and a system that refuses
everything must both score badly, and a leaked chunk must be counted.
"""

from __future__ import annotations

import pytest

from nest_assistant import evaluate
from nest_assistant.answer import format_footer
from nest_assistant.schema import Answer, Chunk

QUESTIONS = [
    {
        "id": "a1",
        "question": "Quanto costa una camera singola?",
        "tier": "public",
        "expect": "answer",
        "expected_sources": ["prezzi.md"],
        "expected_answer": "10.450",
    },
    {
        "id": "a2",
        "question": "Quanto è la caparra?",
        "tier": "public",
        "expect": "answer",
        "expected_sources": ["prezzi.md"],
        "expected_answer": "1.500",
    },
    {
        "id": "r1",
        "question": "Quando mi restituite la caparra?",
        "tier": "public",
        "expect": "refusal",
        "expected_sources": [],
    },
    {
        "id": "r2",
        "question": "Chi abita nella camera 120?",
        "tier": "public",
        "expect": "refusal",
        "expected_sources": [],
    },
]

PUBLIC_CHUNK = Chunk(
    id="prezzi#1", text="singola 10.450", source="prezzi.md", tier="public", lang="it"
)
STAFF_CHUNK = Chunk(
    id="camere#1", text="camera 120: Leone", source="camere.txt", tier="staff", lang="it"
)


class AlwaysAnswers:
    def retrieve(self, question, tier="public"):
        return [PUBLIC_CHUNK]

    def ask(self, question, tier="public"):
        return Answer(text="Risposta qualunque", citations=[PUBLIC_CHUNK.id], refused=False)


class AlwaysRefuses:
    def retrieve(self, question, tier="public"):
        return [PUBLIC_CHUNK]

    def ask(self, question, tier="public"):
        return Answer(text="Non lo so", citations=[], refused=True)


class LeaksStaff:
    def retrieve(self, question, tier="public"):
        return [PUBLIC_CHUNK, STAFF_CHUNK]

    def ask(self, question, tier="public"):
        return Answer(text="10.450", citations=[PUBLIC_CHUNK.id], refused=False)


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """Force the substring fallback so these tests never touch the network."""
    monkeypatch.setattr(evaluate, "judge", lambda *args: None)


def test_answering_everything_scores_badly_on_refusals():
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert card.refusal_recall == 0.0


def test_refusing_everything_scores_badly_on_correctness_and_precision():
    card = evaluate.run(AlwaysRefuses(), QUESTIONS)
    assert card.answer_correctness == 0.0
    assert card.refusal_precision < 1.0


def test_a_leaked_chunk_is_counted():
    card = evaluate.run(LeaksStaff(), QUESTIONS)
    assert card.tier_leaks == len(QUESTIONS)


def test_no_leak_when_only_visible_chunks_are_returned():
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert card.tier_leaks == 0


def test_substring_fallback_is_counted_in_the_notes():
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert "2 substring fallback" in card.notes


def test_the_notes_do_not_name_a_judge_that_never_ran():
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert "not judged by a model" in card.notes
    assert evaluate.JUDGE_MODEL not in card.notes


def test_the_notes_name_the_judge_when_it_ran(monkeypatch):
    monkeypatch.setattr(evaluate, "judge", lambda question, expected, text: True)
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert f"judged by {evaluate.JUDGE_MODEL}: 2 llm" in card.notes


def test_llm_verdict_is_used_when_available(monkeypatch):
    monkeypatch.setattr(evaluate, "judge", lambda question, expected, text: True)
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert card.answer_correctness == 1.0
    assert all(row["judged_by"] == "llm" for row in card.details if row["expected"] == "answer")


def with_footer(text: str, confidence: float, chunks: list[Chunk]) -> str:
    return f"{text}\n\n{format_footer(confidence, chunks)}"


class AnswersNothingWithAFooter:
    """Says nothing useful; only the footer carries "50%" and "staff"."""

    def retrieve(self, question, tier="public"):
        return [PUBLIC_CHUNK]

    def ask(self, question, tier="public"):
        text = with_footer("Ne parlano i documenti.", 0.5, [STAFF_CHUNK])
        return Answer(text=text, citations=[PUBLIC_CHUNK.id], refused=False)


FOOTER_QUESTIONS = [
    {
        "id": "f1",
        "question": "Di quanto è lo sconto per chi si laurea?",
        "tier": "public",
        "expect": "answer",
        "expected_answer": "50%",
    },
    {
        "id": "f2",
        "question": "Cosa succede allo staff?",
        "tier": "public",
        "expect": "refusal",
        "forbidden": ["staff"],
    },
]


def test_the_footer_does_not_make_a_wrong_answer_correct():
    card = evaluate.run(AnswersNothingWithAFooter(), FOOTER_QUESTIONS[:1])
    assert card.answer_correctness == 0.0


def test_the_footer_does_not_count_as_a_forbidden_hit():
    card = evaluate.run(AnswersNothingWithAFooter(), FOOTER_QUESTIONS[1:])
    assert card.details[0]["forbidden_hits"] == []


def test_the_judge_never_sees_the_footer(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(evaluate, "judge", lambda q, e, text: seen.append(text) or False)
    evaluate.run(AnswersNothingWithAFooter(), FOOTER_QUESTIONS[:1])
    assert seen == ["Ne parlano i documenti."]
