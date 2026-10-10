"""ANSWER: grounding, citation validation and refusal.

The model is always faked here (``llm.complete`` is monkeypatched), so these
tests are free, offline and deterministic. They check what *our* code does with
whatever the model says — not whether the model is any good; that is
``make eval``.
"""

from __future__ import annotations

import pytest

from nest_assistant import answer as answer_mod
from nest_assistant import llm
from nest_assistant.answer import (
    _HEDGE_RE,
    REFUSAL_IT,
    REFUSAL_MARKER,
    estimate_confidence,
    generate,
)
from nest_assistant.config import PROMPTS_DIR
from nest_assistant.schema import Chunk

CHUNKS = [
    Chunk(
        id="prezzi.pdf#1",
        text="La camera singola costa 10.450 euro all'anno.",
        source="prezzi.pdf",
        tier="public",
        lang="it",
    ),
    Chunk(
        id="regolamento.pdf#2",
        text="Il silenzio inizia alle 23:00.",
        source="regolamento.pdf",
        tier="resident",
        lang="it",
        section="Silenzio",
    ),
]


def fake_model(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[dict]:
    """Make the model say ``reply``; return the calls it received."""
    calls: list[dict] = []

    def complete(prompt: str, system: str = "", **kwargs) -> str:
        calls.append({"prompt": prompt, "system": system})
        return reply

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def assert_refusal(result) -> None:
    assert result.refused is True
    assert result.text == REFUSAL_IT
    assert result.citations == []
    assert result.confidence == 0.0


# --- grounded answers -------------------------------------------------------


def test_valid_citation_is_kept_and_stripped_from_the_text(monkeypatch):
    fake_model(monkeypatch, "Costa 10.450 euro all'anno [prezzi.pdf#1].")
    result = generate("Quanto costa una singola?", CHUNKS, "it")
    assert result.refused is False
    assert result.citations == ["prezzi.pdf#1"]
    assert "[" not in result.text
    assert result.text == "Costa 10.450 euro all'anno."


def test_several_citations_are_deduplicated_in_order(monkeypatch):
    fake_model(
        monkeypatch,
        "Costa 10.450 euro [prezzi.pdf#1]. Il silenzio è alle 23 [regolamento.pdf#2] "
        "[prezzi.pdf#1].",
    )
    result = generate("domanda", CHUNKS, "it")
    assert result.citations == ["prezzi.pdf#1", "regolamento.pdf#2"]


def test_invented_citation_is_dropped_but_a_real_one_survives(monkeypatch):
    fake_model(monkeypatch, "Costa 10.450 euro [prezzi.pdf#1] [inventato.pdf#99].")
    result = generate("domanda", CHUNKS, "it")
    assert result.refused is False
    assert result.citations == ["prezzi.pdf#1"]
    assert "inventato" not in result.text


def test_prompt_shows_the_model_every_chunk_id_and_the_question(monkeypatch):
    calls = fake_model(monkeypatch, "Sì [prezzi.pdf#1].")
    generate("Quanto costa una singola?", CHUNKS, "it")
    prompt = calls[0]["prompt"]
    assert "[prezzi.pdf#1]" in prompt
    assert "[regolamento.pdf#2]" in prompt
    assert "sezione: Silenzio" in prompt
    assert "Quanto costa una singola?" in prompt


def test_the_system_prompt_comes_from_the_prompts_file(monkeypatch):
    calls = fake_model(monkeypatch, "Sì [prezzi.pdf#1].")
    generate("domanda", CHUNKS, "it")
    expected = (PROMPTS_DIR / "answer_system.it.md").read_text(encoding="utf-8")
    assert calls[0]["system"] == expected


def test_unknown_language_falls_back_to_the_italian_prompt():
    assert answer_mod.load_system_prompt("xx") == answer_mod.load_system_prompt("it")


# --- refusals ---------------------------------------------------------------


def test_no_chunks_never_calls_the_model(monkeypatch):
    calls = fake_model(monkeypatch, "Costa 10 euro [x#1].")
    assert_refusal(generate("Quanto costa?", [], "it"))
    assert calls == []


def test_model_marker_becomes_the_refusal_message(monkeypatch):
    fake_model(monkeypatch, REFUSAL_MARKER)
    result = generate("Quando restituite la caparra?", CHUNKS, "it")
    assert_refusal(result)
    assert REFUSAL_MARKER not in result.text


def test_marker_with_extra_text_is_still_a_refusal(monkeypatch):
    fake_model(monkeypatch, f"{REFUSAL_MARKER} (forse entro 30 giorni)")
    assert_refusal(generate("Quando restituite la caparra?", CHUNKS, "it"))


def test_answer_without_any_citation_is_a_refusal(monkeypatch):
    """No citation means the model spoke from memory."""
    fake_model(monkeypatch, "La caparra viene restituita entro 30 giorni.")
    assert_refusal(generate("Quando restituite la caparra?", CHUNKS, "it"))


def test_answer_citing_only_invented_ids_is_a_refusal(monkeypatch):
    fake_model(monkeypatch, "Entro 30 giorni [inventato.pdf#7].")
    assert_refusal(generate("Quando restituite la caparra?", CHUNKS, "it"))


@pytest.mark.parametrize("reply", ["", "   ", "\n"])
def test_empty_model_reply_is_a_refusal(monkeypatch, reply):
    fake_model(monkeypatch, reply)
    assert_refusal(generate("domanda", CHUNKS, "it"))


def test_citation_only_reply_is_a_refusal(monkeypatch):
    fake_model(monkeypatch, "[prezzi.pdf#1]")
    assert_refusal(generate("domanda", CHUNKS, "it"))


@pytest.mark.parametrize(
    "error", [llm.LLMUnavailable("no key"), RuntimeError("boom"), TimeoutError()]
)
def test_generate_never_raises_when_the_model_fails(monkeypatch, error):
    def broken(prompt: str, system: str = "", **kwargs) -> str:
        raise error

    monkeypatch.setattr(llm, "complete", broken)
    assert_refusal(generate("domanda", CHUNKS, "it"))


def test_refusal_message_points_to_the_secretariat():
    assert "segreteria" in REFUSAL_IT.lower()


# --- confidence -------------------------------------------------------------


def test_confidence_is_zero_on_refusal_and_never_certain_otherwise(monkeypatch):
    assert generate("domanda", [], "it").confidence == 0.0
    fake_model(monkeypatch, "Sì [prezzi.pdf#1] [regolamento.pdf#2].")
    assert 0.0 < generate("domanda", CHUNKS, "it").confidence < 1.0


def test_two_supporting_chunks_beat_one(monkeypatch):
    fake_model(monkeypatch, "Sì [prezzi.pdf#1].")
    one = generate("domanda", CHUNKS, "it").confidence
    fake_model(monkeypatch, "Sì [prezzi.pdf#1] [regolamento.pdf#2].")
    two = generate("domanda", CHUNKS, "it").confidence
    assert two > one


def test_an_invented_citation_lowers_confidence(monkeypatch):
    fake_model(monkeypatch, "Sì [prezzi.pdf#1].")
    clean = generate("domanda", CHUNKS, "it").confidence
    fake_model(monkeypatch, "Sì [prezzi.pdf#1] [inventato.pdf#9].")
    assert generate("domanda", CHUNKS, "it").confidence < clean


def test_admitting_a_gap_lowers_confidence(monkeypatch):
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1].")
    sure = generate("domanda", CHUNKS, "it").confidence
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1]. I documenti non specificano altro.")
    assert generate("domanda", CHUNKS, "it").confidence < sure


@pytest.mark.parametrize(
    ("cited", "invented", "text", "expected"),
    [
        (["a.pdf#1"], 0, "Costa 10 euro.", 0.6),
        (["a.pdf#1", "b.pdf#2"], 0, "Costa 10 euro.", 0.7),
        (["a.pdf#1", "a.pdf#2"], 0, "Costa 10 euro.", 0.6),  # same document: no bonus
        (["a.pdf#1"], 1, "Costa 10 euro.", 0.4),
        (["a.pdf#1"], 0, "Costa 10 euro. I documenti non specificano altro.", 0.4),
        (["a.pdf#1"], 1, "Costa 10 euro. I documenti non specificano altro.", 0.2),
        (["a.pdf#1", "b.pdf#2"], 1, "Costa 10 euro. I documenti non dicono altro.", 0.3),
    ],
)
def test_confidence_values(cited, invented, text, expected):
    assert estimate_confidence(text, cited, invented) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I documenti non specificano il prezzo.",
        "Non è stato possibile trovare il dato.",
        "Non sono presenti dettagli sui pasti.",
        "Non risultano altre informazioni.",
        "The documents do not specify the price.",
        "The document does not mention meals.",
    ],
)
def test_admitted_gaps_are_recognised(text):
    assert _HEDGE_RE.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sono inclusi non solo la colazione ma anche la cena.",
        "La retta non include il parcheggio, che costa 50 euro.",
        "Il silenzio inizia alle 23:00.",
        "Costs 10,450 euros per year.",
    ],
)
def test_ordinary_answers_are_not_read_as_admitted_gaps(text):
    assert not _HEDGE_RE.search(text)


def test_a_hedged_answer_is_lowered_not_refused(monkeypatch):
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1]. I documenti non dicono altro.")
    result = generate("domanda", CHUNKS, "it")
    assert result.refused is False
    assert result.confidence == 0.4
