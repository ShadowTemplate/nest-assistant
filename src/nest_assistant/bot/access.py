"""Who may use the bot while it is in testing.

``data/bot_testers.json`` — **gitignored**, it holds real Telegram ids::

    {"telegram:111111111": "Nome Cognome", "telegram:222222222": "Altro Nome"}

Each person keeps their own copy, locally, and never commits it: ``data/`` is
gitignored on purpose. Point ``NEST_BOT_TESTERS`` at a different path if you
prefer to keep the file elsewhere.

The file is read on every message, so adding someone needs no restart.

This is *not* ``identity``: that decides what a user may **see** (tier), and an
unknown id there is ``public`` and still gets an answer. This decides whether the
user gets an answer **at all**, and an unknown id here gets nothing — every answer
costs money.

Closed by default: a missing, empty or corrupt file lets nobody in. The limit is
lifted only by ``NEST_BOT_OPEN=1`` in ``.env``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import DATA_DIR

TESTERS_PATH = Path(os.environ.get("NEST_BOT_TESTERS", DATA_DIR / "bot_testers.json"))


def is_open() -> bool:
    """True only when ``NEST_BOT_OPEN`` is exactly ``1``. Anything else is closed."""
    return os.environ.get("NEST_BOT_OPEN", "0").strip() == "1"


def load_testers() -> dict[str, str]:
    """The allowed ids, or an empty dict if the file is missing or unreadable."""
    try:
        raw = json.loads(TESTERS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def is_allowed(user_id: str) -> bool:
    """May ``user_id`` use the bot? Never raises."""
    try:
        return is_open() or user_id in load_testers()
    except Exception:  # noqa: BLE001 - when in doubt, nobody gets in
        return False


NOT_ALLOWED_IT = (
    "Ciao! Questo bot è in fase di test e per ora è riservato a poche persone. "
    "Se vuoi provarlo, manda questo codice a chi lo gestisce:\n\n{user_id}"
)
