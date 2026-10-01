"""One test per interface.

These test the **contract**, not the implementation — they must still pass after
a team replaces its stub with the real thing. If your real implementation breaks
one of these, the test is right and the implementation is wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nest_assistant import answer as answer_mod
from nest_assistant import evaluate, identity, index, ingest
from nest_assistant.bot import handle_message
from nest_assistant.schema import TIERS, Answer, Chunk, tier_allows
from nest_assistant.storage import read_chunks, write_chunks

# --- TEAM 1 — INGEST --------------------------------------------------------


def test_build_chunks_returns_valid_chunks():
    chunks = ingest.build_chunks()
    assert chunks, "ingest must return at least one chunk"
    for chunk in chunks:
        assert isinstance(chunk, Chunk)
        assert chunk.id and chunk.text and chunk.source
        assert chunk.tier in TIERS
        assert chunk.lang in {"it", "en"}


def test_chunk_ids_are_unique():
    """A duplicate id makes a citation ambiguous, which makes it worthless."""
    chunks = ingest.build_chunks()
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_ids_are_stable_across_runs():
    assert [c.id for c in ingest.build_chunks()] == [c.id for c in ingest.build_chunks()]


def test_chunks_roundtrip_through_the_file_index_reads(tmp_path: Path):
    path = tmp_path / "chunks.jsonl"
    original = ingest.build_chunks()
    assert write_chunks(original, path) == len(original)
    assert read_chunks(path) == original


# --- TEAM 2 — INDEX ---------------------------------------------------------


def test_search_returns_chunks():
    results = index.search("quanto costa una camera singola?", "public", k=3)
    assert isinstance(results, list)
    assert all(isinstance(c, Chunk) for c in results)


def test_search_respects_k():
    assert len(index.search("prezzi", "staff", k=2)) <= 2


@pytest.mark.skip(
    reason="TEAM 2 — task W1-2.2. Delete this line and make the test pass. "
    "Until you do, `make eval` reports tier leaks and the board stays red."
)
def test_public_never_sees_private():
    """A `public` caller must never receive a resident or staff chunk.

    Not ranked last. Not returned with a warning. Never returned.

    Try it against every question in eval/questions.yaml, not just this one —
    the leak you have not thought of is the one that matters.
    """
    for tier in TIERS:
        for question in ["morosità", "regolamento", "prezzi", "procedure interne"]:
            for chunk in index.search(question, tier, k=10):
                assert tier_allows(tier, chunk.tier), (
                    f"{tier} caller received a {chunk.tier} chunk: {chunk.id}"
                )


# --- TEAM 3 — ANSWER --------------------------------------------------------


def test_generate_returns_an_answer():
    chunks = ingest.build_chunks()
    result = answer_mod.generate("Quanto costa una singola?", chunks, "it")
    assert isinstance(result, Answer)
    assert result.text
    assert 0.0 <= result.confidence <= 1.0


def test_generate_refuses_when_there_is_nothing_to_ground_in():
    """No chunks means no answer. This one is not negotiable."""
    result = answer_mod.generate("Posso tenere un gatto?", [], "it")
    assert result.refused is True
    assert result.citations == []


def test_citations_only_reference_supplied_chunks():
    chunks = ingest.build_chunks()
    result = answer_mod.generate("Quanto costa una singola?", chunks, "it")
    supplied = {c.id for c in chunks}
    assert set(result.citations) <= supplied


def test_the_system_prompt_is_a_file_not_a_string():
    """W1-3.1: the prompt is logic, so it is reviewed and versioned like logic."""
    prompt = answer_mod.load_system_prompt("it")
    assert len(prompt) > 200
    assert "Nest" in prompt


# --- TEAM 4 — IDENTITY and BOT ---------------------------------------------


def test_resolve_returns_a_valid_tier():
    assert identity.resolve("telegram:123") in TIERS


def test_resolve_defaults_to_public_for_the_unknown():
    assert identity.resolve("telegram:nobody-has-ever-seen-this") == "public"


@pytest.mark.parametrize("user_id", ["", "garbage", "telegram:", "\n", "'; DROP TABLE--"])
def test_resolve_never_raises(user_id):
    """This runs on every message. It does not get to have a bad day."""
    assert identity.resolve(user_id) in TIERS


def test_bot_handles_the_commands():
    assert "Nest" in handle_message("/start", "telegram:1")
    assert handle_message("/help", "telegram:1")
    assert handle_message("/reset", "telegram:1")


def test_bot_answers_a_question():
    reply = handle_message("Quanto costa una camera singola?", "telegram:1")
    assert isinstance(reply, str) and reply


# --- TEAM 5 — EVAL ----------------------------------------------------------


def test_questions_file_is_well_formed():
    questions = evaluate.load_questions()
    assert questions, "eval/questions.yaml is empty — that is task W1-5.1"
    for item in questions:
        assert item["id"] and item["question"]
        assert item["tier"] in TIERS
        assert item["expect"] in {"answer", "refusal"}


def test_question_ids_are_unique():
    ids = [q["id"] for q in evaluate.load_questions()]
    assert len(ids) == len(set(ids))


def test_the_set_contains_questions_that_must_be_refused():
    """A set with no unanswerable questions cannot measure hallucination."""
    expectations = {q["expect"] for q in evaluate.load_questions()}
    assert "refusal" in expectations
    assert "answer" in expectations


def test_eval_runs_and_produces_a_scorecard():
    from nest_assistant.pipeline import Pipeline

    scorecard = evaluate.run(Pipeline())
    assert scorecard.n_questions > 0
    assert 0.0 <= scorecard.retrieval_hit_rate <= 1.0
    assert 0.0 <= scorecard.answer_correctness <= 1.0
    assert scorecard.tier_leaks >= 0
