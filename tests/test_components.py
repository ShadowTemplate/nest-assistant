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
from nest_assistant.config import embedding_model_cached
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
    assert index.search("prezzi", "staff", k=0) == []


def test_search_is_ranked_best_first():
    scores = [s for _, s in index.search_with_scores("quanto costa una singola?", "staff", k=10)]
    assert scores == sorted(scores, reverse=True)


def test_search_is_deterministic():
    """EVAL compares October with March: the same query must rank the same way."""
    first = [(c.id, s) for c, s in index.search_with_scores("orari silenzio", "staff", k=10)]
    for _ in range(3):
        assert [
            (c.id, s) for c, s in index.search_with_scores("orari silenzio", "staff", 10)
        ] == first


@pytest.mark.skipif(
    not embedding_model_cached(),
    reason="embedding model not downloaded — run `make warm`",
)
def test_search_matches_meaning_not_words(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The question shares no content word with the right chunk (costa ≠ retta)."""
    corpus = [
        Chunk("silenzio#1", "Il silenzio è richiesto dalle 23 alle 7.", "r.md", "public", "it"),
        Chunk("prezzi#1", "Retta annuale camera singola: 10.450 euro.", "p.md", "public", "it"),
        Chunk(
            "palestra#1", "La palestra apre alle 6 e chiude a mezzanotte.", "r.md", "public", "it"
        ),
    ]
    _tiny_corpus(monkeypatch, tmp_path, corpus)
    assert index.search("quanto costa una stanza singola?", "public", k=1)[0].id == "prezzi#1"


def _tiny_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, corpus: list[Chunk]) -> None:
    """Search ``corpus`` instead of the real one, with its index in ``tmp_path``."""
    monkeypatch.setattr(index, "load_corpus", lambda: corpus)
    monkeypatch.setattr(index, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(index, "EMBEDDINGS_PATH", tmp_path / "embeddings.npy")
    monkeypatch.setattr(index, "META_PATH", tmp_path / "meta.json")


def test_keywords_normalise_the_way_people_type():
    """Accents, stopwords and Italian endings must not stop a match."""
    assert index._tokens("il colloquio si puo fare online?") == index._tokens(
        "Il colloquio si può fare online"
    )
    assert index._tokens("camera singola") == index._tokens("camere singole")
    assert "10.450" in index._tokens("Singola: 10.450 €") and "23:00" in index._tokens("alle 23:00")


def test_without_a_model_search_ranks_by_keywords(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`make setup-lite` and CI have no embedding model: still rank, never in document order."""
    corpus = [
        Chunk("palestra#1", "La palestra apre alle 6.", "r.md", "public", "it"),
        Chunk("caparra#1", "La caparra è di 1.500 euro.", "p.md", "public", "it"),
    ]
    _tiny_corpus(monkeypatch, tmp_path, corpus)

    def no_model(*_args: object) -> None:
        raise RuntimeError("no model")

    monkeypatch.setattr(index, "_rank_vector", no_model)
    assert index.search("quanto è la caparra?", "public", k=2)[0].id == "caparra#1"


@pytest.mark.skipif(
    not embedding_model_cached(),
    reason="embedding model not downloaded — run `make warm`",
)
def test_hybrid_only_reorders_what_meaning_picked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keywords may sharpen the order of meaning's top 5, never change which chunks they are."""
    corpus = [
        Chunk(f"c#{n}", text, "x.md", "public", "it")
        for n, text in enumerate(
            [
                "Retta annuale camera singola: 10.450 euro.",
                "Camera doppia: 8.250 euro all'anno.",
                "La caparra è di 1.500 euro.",
                "Il silenzio è richiesto dalle 23 alle 7.",
                "La palestra chiude a mezzanotte.",
                "Gli ospiti vanno annunciati in reception.",
                "Il bucato si fa al piano terra.",
            ]
        )
    ]
    _tiny_corpus(monkeypatch, tmp_path, corpus)
    for question in ["quanto costa una singola?", "orari palestra", "posso invitare amici?"]:
        vector = {c.id for c, _ in index.search_with_scores(question, "public", 5, "vector")}
        hybrid = {c.id for c in index.search(question, "public", k=5)}
        assert hybrid == vector


@pytest.mark.skipif(
    not embedding_model_cached(),
    reason="embedding model not downloaded — run `make warm`",
)
def test_search_uses_the_hybrid_ranking(monkeypatch: pytest.MonkeyPatch):
    """search() is what the pipeline calls: it must rank with keywords fused into meaning.

    Checks the call, not just the output, so a docstring and the code cannot
    drift apart again (PR #14 review).
    """
    calls = []
    real_fuse = index._fuse

    def spy(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return real_fuse(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(index, "_fuse", spy)
    question = "quanto costa una camera singola?"
    results = [c.id for c in index.search(question, "staff", k=5)]
    assert calls, "search() did not fuse keywords into the meaning ranking"
    assert results == [c.id for c, _ in index.search_with_scores(question, "staff", 5, "hybrid")]


def test_public_never_sees_private():
    """A `public` caller must never receive a resident or staff chunk.

    Not ranked last. Not returned with a warning. Never returned.

    Try it against every question in eval/questions.yaml, not just this one —
    the leak you have not thought of is the one that matters.
    """
    questions = ["morosità", "regolamento", "prezzi", "procedure interne"]
    questions += [q["question"] for q in evaluate.load_questions(corpus="all")]
    for tier in TIERS:
        for question in questions:
            for chunk in index.search(question, tier, k=100):
                assert tier_allows(tier, chunk.tier), (
                    f"{tier} caller received a {chunk.tier} chunk: {chunk.id}"
                )


def test_chunk_with_broken_tier_is_hidden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A typo in a tier label must hide the chunk, not show it to everyone."""
    corpus = [
        Chunk("ok#1", "Orari della mensa.", "a.md", "public", "it"),
        Chunk("typo#1", "Procedura morosità.", "b.md", "Staff ", "it"),  # type: ignore[arg-type]
    ]
    _tiny_corpus(monkeypatch, tmp_path, corpus)
    for tier in TIERS:
        assert [c.id for c in index.search("morosità", tier, k=10)] == ["ok#1"]


def test_unknown_caller_tier_is_refused():
    with pytest.raises(ValueError):
        index.search("prezzi", "admin", k=5)  # type: ignore[arg-type]


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


def test_saved_scorecard_withholds_non_public_answers(tmp_path, monkeypatch):
    """The committed scorecard must not quote resident or staff documents."""
    from nest_assistant.schema import Scorecard

    monkeypatch.setattr(evaluate, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(evaluate, "FULL_RESULTS_DIR", tmp_path / "build")
    card = Scorecard(
        n_questions=3,
        details=[
            {"id": "a", "tier": "public", "answer": "costa 10.450 euro"},
            {"id": "b", "tier": "resident", "answer": "la password è segreta123"},
            {"id": "c", "tier": "staff", "answer": "in camera 120 abita Leone"},
        ],
    )
    committed = evaluate.save(card, "test").read_text(encoding="utf-8")
    assert "10.450" in committed
    assert "segreta123" not in committed and "Leone" not in committed
    full = tmp_path / "build"
    assert any("segreta123" in f.read_text(encoding="utf-8") for f in full.glob("*.json"))


def test_eval_runs_and_produces_a_scorecard():
    from nest_assistant.pipeline import Pipeline

    scorecard = evaluate.run(Pipeline())
    assert scorecard.n_questions > 0
    assert 0.0 <= scorecard.retrieval_hit_rate <= 1.0
    assert 0.0 <= scorecard.answer_correctness <= 1.0
    assert scorecard.tier_leaks >= 0


def test_answer_footer_shows_confidence_and_privilege(monkeypatch: pytest.MonkeyPatch):
    chunks = [
        Chunk("a#1", "La singola costa 600 euro.", "a.md", "public", "it"),
        Chunk("b#1", "Orari di silenzio dalle 23.", "b.md", "resident", "it"),
    ]
    monkeypatch.setattr(
        answer_mod.llm, "complete", lambda *a, **k: "Costa 600 euro [a#1]. Silenzio dalle 23 [b#1]."
    )
    result = answer_mod.generate("domanda", chunks, "it")
    assert result.confidence == 0.8  # two documents: CONFIDENCE_CORROBORATED
    assert result.text.endswith("Affidabilità: 80% · Livello: residente__")
    assert "[a#1]" not in result.text
