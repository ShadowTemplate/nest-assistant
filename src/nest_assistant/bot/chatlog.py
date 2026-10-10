"""Chat logs for the bot: one folder per person, one file per session.

Everything lives under ``data/logs/`` — **gitignored**, because it holds Telegram
ids and what people typed. See ``docs/DATA_POLICY.md``.

::

    data/logs/
    ├── Nome-Cognome_telegram-111111111/
    │   ├── 2026-10-10_12-50-58.jsonl     one session
    │   └── 2026-10-10_14-02-11.jsonl     the next one, after a /reset
    ├── FAIL/
    │   └── Nome-Cognome_telegram-111111111/
    │       └── 2026-10-10_12-50-58.jsonl     only the failed exchanges of that session
    └── _RIFIUTATI/
        └── telegram-123456/2026-10-10.jsonl  people who are not on the testers list

A session starts at a person's first message and ends at ``/reset`` (see
:func:`end_session`). The bot keeps the current session in memory, so after a
restart the next message opens a new one.

The folder is named after the testers file when the id is in it, and found again
by id if the name later changes — history is never split. Logging must never take
the bot down, so nothing here raises.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR
from .access import load_testers

LOG_DIR = DATA_DIR / "logs"
FAIL_DIR = LOG_DIR / "FAIL"
DENIED_DIR = LOG_DIR / "_RIFIUTATI"

log = logging.getLogger("nest_assistant.bot.chatlog")

_lock = threading.Lock()
_sessions: dict[str, str] = {}  # user_id -> session file stem


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text).strip("-") or "utente"


def _user_dir(parent: Path, user_id: str, name: str | None) -> Path:
    """The person's folder under ``parent``: an existing one with this id, else new."""
    key = _slug(user_id)
    if parent.is_dir():
        for d in parent.iterdir():
            if d.is_dir() and (d.name == key or d.name.endswith("_" + key)):
                return d
    return parent / (f"{_slug(name)}_{key}" if name else key)


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def end_session(user_id: str) -> None:
    """Close the person's current session; their next message opens a new one."""
    with _lock:
        _sessions.pop(user_id, None)


def log_exchange(
    *,
    user_id: str,
    chat_id: int | None,
    question: str,
    answer: str,
    duration_ms: int,
    error: BaseException | None = None,
    denied: bool = False,
) -> None:
    """Record one question/answer. ``error`` set means the request failed.

    ``denied`` is a person who is not on the testers list: logged as not ok, in
    ``_RIFIUTATI/``, and it is not an error, so it never reaches ``FAIL/``.
    """
    try:
        now = datetime.now().astimezone()
        record = {
            "time": now.isoformat(timespec="seconds"),
            "user_id": user_id,
            "chat_id": chat_id,
            "question": question,
            "answer": answer,
            "ok": error is None and not denied,
            "error": "non autorizzato"
            if denied
            else None
            if error is None
            else f"{type(error).__name__}: {error}",
            "duration_ms": duration_ms,
        }
        if denied:
            _append(_user_dir(DENIED_DIR, user_id, None) / f"{now:%Y-%m-%d}.jsonl", record)
            return

        name = load_testers().get(user_id)
        with _lock:
            session = _sessions.setdefault(user_id, f"{now:%Y-%m-%d_%H-%M-%S}")
        _append(_user_dir(LOG_DIR, user_id, name) / f"{session}.jsonl", record)

        if error is not None:
            detail = dict(record)
            detail["traceback"] = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            _append(_user_dir(FAIL_DIR, user_id, name) / f"{session}.jsonl", detail)
    except Exception:  # noqa: BLE001 - a full disk must not kill the bot
        log.exception("could not write the chat log")
