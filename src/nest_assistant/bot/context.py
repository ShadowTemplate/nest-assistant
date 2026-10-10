"""Conversation context: make "E la doppia?" mean something to the retriever.

The index sees one question at a time. "E la doppia?" on its own is a search for
the word *doppia*; it has no idea we were talking about prices. So before the
pipeline runs, a follow-up is rewritten into a standalone question
("Quanto costa una camera doppia?") from the person's recent messages.

"Recent" is a time window, not a message count: a question asked an hour ago is
probably another conversation, and mixing it in would make the rewrite worse.
Every message carries its timestamp so the model can judge that too. The window
(:data:`~nest_assistant.config.CONTEXT_WINDOW_MINUTES`) and a cap on exchanges
(:data:`~nest_assistant.config.CONTEXT_MAX_TURNS`) keep the prompt short.

The history lives in memory, per ``user_id``, and is lost on restart — a stale
conversation is worth nothing after a restart anyway. Nothing here raises, and
with no recent history, no API key or a model failure the original question is
used unchanged, so the bot is never worse than it was without context.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .. import llm
from ..config import CONTEXT_MAX_TURNS, CONTEXT_WINDOW_MINUTES, PROMPTS_DIR

log = logging.getLogger("nest_assistant.bot.context")

MAX_ANSWER_CHARS = 300
"""Answers are trimmed in the prompt: the question matters more than the prose."""

MAX_REWRITE_CHARS = 500
"""A "question" longer than this is the model rambling; use the original."""


@dataclass(frozen=True)
class Turn:
    time: datetime
    question: str  # standalone version, so follow-ups chain ("E per due persone?")
    answer: str


_lock = threading.Lock()
_history: dict[str, deque[Turn]] = {}  # user_id -> recent turns, oldest first


def _now() -> datetime:
    return datetime.now().astimezone()


def recent_turns(user_id: str, now: datetime | None = None) -> list[Turn]:
    """The person's turns inside the time window, oldest first, capped."""
    now = now or _now()
    cutoff = now - timedelta(minutes=CONTEXT_WINDOW_MINUTES)
    with _lock:
        turns = [t for t in _history.get(user_id, ()) if t.time >= cutoff]
    return turns[-CONTEXT_MAX_TURNS:]


def record(user_id: str, question: str, answer: str, now: datetime | None = None) -> None:
    """Remember one exchange. Old ones fall out of the deque on their own."""
    now = now or _now()
    with _lock:
        turns = _history.setdefault(user_id, deque(maxlen=CONTEXT_MAX_TURNS))
        turns.append(Turn(time=now, question=question, answer=answer))


def clear(user_id: str) -> None:
    """Forget the person's conversation (``/reset``)."""
    with _lock:
        _history.pop(user_id, None)


def _load_prompt() -> str:
    return (PROMPTS_DIR / "context_rewrite.it.md").read_text(encoding="utf-8")


def _shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_prompt(turns: list[Turn], question: str, now: datetime) -> str:
    """The user message for the rewriter: timestamped conversation, then the question."""
    lines: list[str] = []
    for t in turns:
        stamp = f"{t.time:%Y-%m-%d %H:%M}"
        lines.append(f"[{stamp}] Utente: {_shorten(t.question, MAX_REWRITE_CHARS)}")
        lines.append(f"[{stamp}] Assistente: {_shorten(t.answer, MAX_ANSWER_CHARS)}")
    lines.append(f"[{now:%Y-%m-%d %H:%M}] Utente: {_shorten(question, MAX_REWRITE_CHARS)}")
    return "\n".join(lines)


def standalone_question(user_id: str, question: str, now: datetime | None = None) -> str:
    """``question`` rewritten to make sense without the conversation.

    Returns ``question`` itself when there is nothing to add: no recent history
    (no model call at all), no key, or the model failed or answered nonsense.
    """
    now = now or _now()
    turns = recent_turns(user_id, now)
    if not turns or not question.strip():
        return question
    try:
        rewritten = llm.complete(
            build_prompt(turns, question, now),
            system=_load_prompt(),
            max_tokens=200,
        )
    except llm.LLMUnavailable:
        return question
    except Exception:  # noqa: BLE001 - context is a nicety, it must not take the bot down
        log.exception("question rewrite failed")
        return question

    rewritten = rewritten.strip()
    if not rewritten or "\n" in rewritten or len(rewritten) > MAX_REWRITE_CHARS:
        return question
    return rewritten


__all__ = ["standalone_question", "record", "clear", "recent_turns", "build_prompt", "Turn"]
