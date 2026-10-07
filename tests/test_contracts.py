"""The contracts in ``schema.py``.

If a test here fails, six teams are about to disagree with each other.
"""

from __future__ import annotations

import pytest

from nest_assistant.schema import TIERS, Answer, Chunk, Scorecard, tier_allows, tier_rank


def test_tiers_are_ordered_by_privilege():
    assert tier_rank("public") < tier_rank("resident") < tier_rank("staff")


@pytest.mark.parametrize(
    ("caller", "required", "expected"),
    [
        ("public", "public", True),
        ("public", "resident", False),
        ("public", "staff", False),
        ("resident", "public", True),
        ("resident", "resident", True),
        ("resident", "staff", False),
        ("staff", "public", True),
        ("staff", "resident", True),
        ("staff", "staff", True),
    ],
)
def test_tier_allows(caller, required, expected):
    assert tier_allows(caller, required) is expected


def test_tier_ordering_does_not_rely_on_the_alphabet():
    """Comparing the tier strings directly happens to work today. Do not.

    ``"public" < "resident" < "staff"`` alphabetically, which is the same order
    as their privilege — a coincidence, and a trap. The day somebody adds
    ``"admin"`` or ``"manager"``, every ``<`` comparison silently starts giving
    the wrong answer, and the wrong answer here is a leaked document.

    :func:`tier_allows` cannot break that way, because it compares rank.
    """
    assert sorted(TIERS) == list(TIERS)  # today's coincidence
    assert not tier_allows("public", "resident")

    hypothetical = "admin"  # sorts before "public"; would outrank everything
    assert hypothetical < "public"
    with pytest.raises(ValueError):
        tier_rank(hypothetical)  # tier_allows refuses to guess instead


def test_unknown_tier_is_an_error_not_a_default():
    with pytest.raises(ValueError):
        tier_rank("admin")


def test_chunk_roundtrips_through_jsonl():
    chunk = Chunk(
        id="regolamento.md#12",
        text="Il silenzio è richiesto dalle 23:00.",
        source="regolamento.md",
        tier="resident",
        lang="it",
        section="Convivenza",
    )
    assert Chunk.from_dict(chunk.to_dict()) == chunk


def test_answer_defaults_are_the_safe_ones():
    answer = Answer(text="…")
    assert answer.citations == []
    assert answer.confidence == 0.0
    assert answer.refused is False


def test_scorecard_summary_flags_a_leak():
    assert "OK" in Scorecard(tier_leaks=0).summary()
    assert "FAIL" in Scorecard(tier_leaks=1).summary()


def test_every_tier_is_covered_by_the_literal():
    assert set(TIERS) == {"public", "resident", "staff"}


def test_embedding_model_cache_check(tmp_path, monkeypatch):
    """make check warns about a missing embedding model; this is how it knows."""
    from nest_assistant.config import embedding_model_cached

    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert not embedding_model_cached("org/model")
    (tmp_path / "models--org--model" / "snapshots" / "abc123").mkdir(parents=True)
    assert embedding_model_cached("org/model")
