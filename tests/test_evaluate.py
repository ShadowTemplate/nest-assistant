"""TEAM 5 — EVAL: the harness must not be gameable, and must count leaks.

These tests use fake pipelines, so they run offline with no key. They check the
scorer itself: a system that answers everything and a system that refuses
everything must both score badly, and a leaked chunk must be counted.
"""

from __future__ import annotations

import pytest

from nest_assistant import evaluate
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
    assert "substring fallback" in card.notes
    assert "0 llm" in card.notes


def test_llm_verdict_is_used_when_available(monkeypatch):
    monkeypatch.setattr(evaluate, "judge", lambda question, expected, text: True)
    card = evaluate.run(AlwaysAnswers(), QUESTIONS)
    assert card.answer_correctness == 1.0
    assert all(row["judged_by"] == "llm" for row in card.details if row["expected"] == "answer")
