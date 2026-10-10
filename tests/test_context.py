"""Conversation context: follow-ups are rewritten, stale chats are not.

The model is faked: tests never call a paid one (see conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nest_assistant import bot, llm
from nest_assistant.bot import context
from nest_assistant.config import CONTEXT_MAX_TURNS, CONTEXT_WINDOW_MINUTES

T0 = datetime(2026, 10, 10, 10, 30, tzinfo=UTC)
USER = "telegram:1"


@pytest.fixture(autouse=True)
def clean_history():
    context.clear(USER)
    context.clear("telegram:2")
    yield
    context.clear(USER)
    context.clear("telegram:2")


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace llm.complete; the returned list records every prompt it was sent."""
    calls: list[dict] = []

    def complete(prompt, system="", **kwargs):
        calls.append({"prompt": prompt, "system": system})
        return "Quanto costa una camera doppia?"

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def test_a_first_question_is_left_alone_and_costs_no_model_call(fake_llm):
    assert context.standalone_question(USER, "Quanto costa una singola?", T0) == (
        "Quanto costa una singola?"
    )
    assert fake_llm == []


def test_a_follow_up_is_rewritten_from_the_recent_exchange(fake_llm):
    context.record(USER, "Quanto costa una singola?", "450 € al mese.", T0)
    later = T0 + timedelta(minutes=2)

    result = context.standalone_question(USER, "E la doppia?", later)

    assert result == "Quanto costa una camera doppia?"
    prompt = fake_llm[0]["prompt"]
    assert "Quanto costa una singola?" in prompt
    assert "450 € al mese." in prompt
    assert "E la doppia?" in prompt
    assert "2026-10-10 10:30" in prompt  # the earlier exchange is timestamped...
    assert "2026-10-10 10:32" in prompt  # ...and so is the new question
    assert fake_llm[0]["system"]  # the prompt file was loaded


def test_messages_older_than_the_window_are_not_used(fake_llm):
    context.record(USER, "Quanto costa una singola?", "450 € al mese.", T0)
    much_later = T0 + timedelta(minutes=CONTEXT_WINDOW_MINUTES + 1)

    assert context.standalone_question(USER, "E la doppia?", much_later) == "E la doppia?"
    assert fake_llm == []


def test_only_the_most_recent_turns_are_sent(fake_llm):
    for i in range(CONTEXT_MAX_TURNS + 3):
        context.record(USER, f"domanda {i}", f"risposta {i}", T0)

    context.standalone_question(USER, "e poi?", T0 + timedelta(minutes=1))

    prompt = fake_llm[0]["prompt"]
    assert f"domanda {CONTEXT_MAX_TURNS + 2}" in prompt
    assert "domanda 0" not in prompt


def test_people_do_not_share_a_conversation(fake_llm):
    context.record(USER, "Quanto costa una singola?", "450 €", T0)
    assert context.standalone_question("telegram:2", "E la doppia?", T0) == "E la doppia?"


def test_clear_forgets_the_conversation(fake_llm):
    context.record(USER, "Quanto costa una singola?", "450 €", T0)
    context.clear(USER)
    assert context.standalone_question(USER, "E la doppia?", T0) == "E la doppia?"


def test_no_key_means_the_original_question(monkeypatch):
    """conftest blanks the key, so the real llm.complete raises LLMUnavailable."""
    context.record(USER, "Quanto costa una singola?", "450 €", T0)
    assert context.standalone_question(USER, "E la doppia?", T0) == "E la doppia?"


@pytest.mark.parametrize("bad", ["", "   ", "riga uno\nriga due", "x" * 600])
def test_a_useless_rewrite_falls_back_to_the_original(monkeypatch, bad):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: bad)
    context.record(USER, "Quanto costa una singola?", "450 €", T0)
    assert context.standalone_question(USER, "E la doppia?", T0) == "E la doppia?"


def test_a_crashing_model_never_reaches_the_user(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "complete", explode)
    context.record(USER, "Quanto costa una singola?", "450 €", T0)
    assert context.standalone_question(USER, "E la doppia?", T0) == "E la doppia?"


# --- through handle_message ------------------------------------------------


class _SpyPipeline:
    def __init__(self):
        self.questions: list[str] = []

    def ask(self, question, tier="public"):
        from nest_assistant.schema import Answer

        self.questions.append(question)
        return Answer(text=f"risposta a {question}", citations=[], confidence=1.0, refused=False)


def test_the_pipeline_receives_the_standalone_question(fake_llm):
    spy = _SpyPipeline()
    bot.handle_message("Quanto costa una singola?", USER, spy)
    bot.handle_message("E la doppia?", USER, spy)
    assert spy.questions == ["Quanto costa una singola?", "Quanto costa una camera doppia?"]


def test_reset_starts_a_fresh_conversation(fake_llm):
    spy = _SpyPipeline()
    bot.handle_message("Quanto costa una singola?", USER, spy)
    bot.handle_message("/reset", USER, spy)
    bot.handle_message("E la doppia?", USER, spy)
    assert spy.questions[-1] == "E la doppia?"
    assert fake_llm == []


def test_commands_are_not_remembered(fake_llm):
    spy = _SpyPipeline()
    bot.handle_message("/help", USER, spy)
    assert context.recent_turns(USER) == []
