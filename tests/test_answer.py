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
    CONFIDENCE_CORROBORATED,
    CONFIDENCE_ONE_DOCUMENT,
    REFUSAL_IT,
    REFUSAL_MARKER,
    admits_gap,
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
    assert result.text.startswith("Costa 10.450 euro all'anno.\n\n")


def test_several_citations_are_deduplicated_in_order(monkeypatch):
    fake_model(
        monkeypatch,
        "Costa 10.450 euro [prezzi.pdf#1]. Il silenzio è alle 23 [regolamento.pdf#2] "
        "[prezzi.pdf#1].",
    )
    result = generate("domanda", CHUNKS, "it")
    assert result.citations == ["prezzi.pdf#1", "regolamento.pdf#2"]


def test_an_answer_with_any_invented_citation_is_a_refusal(monkeypatch):
    """One real id does not rescue it: the model made at least part of it up."""
    fake_model(monkeypatch, "Costa 10.450 euro [prezzi.pdf#1] [inventato.pdf#99].")
    assert_refusal(generate("domanda", CHUNKS, "it"))


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


# --- admitted gaps ----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I documenti non specificano il prezzo.",
        "I documenti non dicono altro.",
        "Non è stato possibile trovare il dato.",
        "Nei documenti la lavanderia risulta tra i servizi, ma non è indicato alcun costo.",
        "Dai documenti emerge solo una descrizione parziale.",
        "The documents do not specify the price.",
        "The document does not mention meals.",
    ],
)
def test_admitted_gaps_are_recognised(text):
    assert admits_gap(text)


@pytest.mark.parametrize(
    "text",
    [
        # Complete answers that happen to contain a negation (review of PR #13).
        "Purtroppo non sono disponibili camere triple.",
        "Non è possibile pagare la caparra in contanti, solo con bonifico.",
        "La retta non include i pasti del sabato.",
        "The fee does not include meals on Saturday.",
        "Gli ospiti non possono restare oltre le 23.",
        "Sono inclusi non solo la colazione ma anche la cena.",
        # "documentazione" is not "documenti": a deadline is not a gap.
        "Devi consegnare la documentazione entro e non oltre il 31/07/2026.",
        "Il silenzio inizia alle 23:00.",
        "Costs 10,450 euros per year.",
    ],
)
def test_ordinary_answers_are_not_read_as_admitted_gaps(text):
    assert not admits_gap(text)


def test_an_answer_that_admits_a_gap_is_a_refusal(monkeypatch):
    """Costa X, ma i documenti non dicono Y: the parent would fill Y with a guess."""
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1]. I documenti non dicono altro.")
    assert_refusal(generate("domanda", CHUNKS, "it"))


def test_a_complete_answer_with_a_negation_is_kept(monkeypatch):
    fake_model(monkeypatch, "Purtroppo non sono disponibili camere triple [prezzi.pdf#1].")
    result = generate("domanda", CHUNKS, "it")
    assert result.refused is False


# --- confidence -------------------------------------------------------------


@pytest.mark.parametrize(
    ("cited", "expected"),
    [
        (["a.pdf#1"], CONFIDENCE_ONE_DOCUMENT),
        (["a.pdf#1", "a.pdf#2"], CONFIDENCE_ONE_DOCUMENT),  # one document, two chunks
        (["a.pdf#1", "b.pdf#2"], CONFIDENCE_CORROBORATED),
    ],
)
def test_confidence_counts_documents_not_chunks(cited, expected):
    assert estimate_confidence(cited) == expected


def test_confidence_has_only_the_declared_levels(monkeypatch):
    assert (CONFIDENCE_ONE_DOCUMENT, CONFIDENCE_CORROBORATED) == (0.6, 0.8)
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1].")
    assert generate("domanda", CHUNKS, "it").confidence == CONFIDENCE_ONE_DOCUMENT
    fake_model(monkeypatch, "Costa 10 euro [prezzi.pdf#1]. Silenzio alle 23 [regolamento.pdf#2].")
    assert generate("domanda", CHUNKS, "it").confidence == CONFIDENCE_CORROBORATED
    assert generate("domanda", [], "it").confidence == 0.0


# --- the traps file ---------------------------------------------------------


def test_refusal_traps_load_with_the_eval_loader():
    """Wired to EVAL's format: question/tier/expect, so evaluate.run() scores them."""
    from nest_assistant import evaluate
    from nest_assistant.config import EVAL_DIR

    items = evaluate.load_questions(EVAL_DIR / "refusal_traps.yaml", corpus="all")
    assert items, "no traps loaded"
    assert {i["expect"] for i in items} == {"refusal", "answer"}
    assert all(i.get("question") and i.get("tier") for i in items)
    assert len({i["id"] for i in items}) == len(items)
