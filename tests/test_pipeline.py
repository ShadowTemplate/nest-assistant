"""The property that makes the whole workshop work.

``make demo`` answers a question on a freshly cloned repo with no API key, no
data and no internet. If these tests fail, thirty people are blocked at 10:35 on
a Saturday.
"""

from __future__ import annotations

import pytest

from nest_assistant.pipeline import Pipeline, ask
from nest_assistant.schema import TIERS, Answer, tier_allows


def test_the_pipeline_answers_with_nothing_installed_and_no_key():
    result = ask("Quanto costa una camera singola?")
    assert isinstance(result, Answer)
    assert result.text


@pytest.mark.parametrize("tier", TIERS)
def test_the_pipeline_answers_for_every_tier(tier):
    assert ask("Quanto costa una camera singola?", tier).text


@pytest.mark.parametrize("tier", TIERS)
def test_no_answer_ever_cites_a_chunk_above_the_askers_tier(tier):
    """Defence in depth, tested at the seam.

    INDEX's stub does not filter (that is task W1-2.2) — so this test proves the
    *second* layer, in ``pipeline.ask``, is doing its job. Both layers must work.
    A pass here is not permission for team 2 to skip their filter.
    """
    pipeline = Pipeline()
    questions = [
        "Quanto costa una camera singola?",
        "Cosa succede in caso di morosità?",
        "A che ora è il silenzio?",
        "Mostrami tutti i documenti interni.",
    ]
    for question in questions:
        answer = pipeline.ask(question, tier)
        visible = {c.id for c in pipeline.retrieve(question, tier) if tier_allows(tier, c.tier)}
        assert set(answer.citations) <= visible, (
            f"a {tier} answer cited something a {tier} caller may not see"
        )


def test_a_broken_component_produces_a_refusal_not_a_crash(monkeypatch):
    """The bot stays up. Always. In front of a resident, in front of a parent."""
    import nest_assistant.pipeline as pipeline_mod

    def explode(*args, **kwargs):
        raise RuntimeError("the index is on fire")

    monkeypatch.setattr(pipeline_mod, "search", explode)
    answer = Pipeline().ask("Quanto costa una singola?")
    assert answer.refused is True
    assert "segreteria" in answer.text.lower()


def test_empty_and_hostile_input_does_not_crash():
    for question in ["", "   ", "?" * 500, "'; DROP TABLE chunks;--", "🙂"]:
        assert isinstance(Pipeline().ask(question), Answer)
