"""TEAM 4 — CHAT · *who is asking?*

You own::

    identity.resolve(user_id: str) -> Tier

Task W1-4.2. The code here is twenty lines and an allowlist. **The real
deliverable is the design note** in ``docs/IDENTITY.md``: how would you actually
verify that someone lives at Nest? At least two options, with their trade-offs,
written for the person who has to implement one in March.

The hard part of this task is not code. It is that "is this person a resident?"
is a question about a process at a reception desk, and no amount of Python
answers it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import DATA_DIR
from ..schema import TIERS, Tier

OWNER = "TEAM 4 — CHAT"
INTERFACE = "identity.resolve(user_id: str) -> Tier"
STATUS = "real"  # flip to "real" when you replace the body below. `make board` reads this.

ALLOWLIST_PATH = Path(os.environ.get("NEST_ALLOWLIST", DATA_DIR / "allowlist.json"))
"""``{"telegram:123456": "resident", "telegram:99": "staff"}``

Lives under ``data/`` — **gitignored**, because it maps real people to real
Telegram ids and that is personal data. See ``docs/DATA_POLICY.md``.
"""


def load_allowlist() -> dict[str, str]:
    """Read the allowlist, or an empty one if it does not exist."""
    if not ALLOWLIST_PATH.exists():
        return {}
    try:
        raw = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


# ---------------------------------------------------------------------------
# TEAM 4 — REPLACE ME
# ---------------------------------------------------------------------------
def resolve(user_id: str) -> Tier:
    """Return the tier of the person behind ``user_id``.

    Contract you must satisfy:

    * **Default to ``"public"``.** Unknown user, malformed id, missing file,
      corrupt file, anything at all — the answer is ``"public"``. Failing open
      means a stranger reads the house rules; failing closed means a resident is
      mildly annoyed. Only one of those is a real problem.
    * Never raise. This runs on every single message.
    * ``user_id`` is namespaced by channel — ``"telegram:123456"`` — so that the
      phone line in 2028 does not collide with Telegram ids.

    The tier comes from the allowlist (``data/allowlist.json``). An id that is not
    listed, or is listed with a value that is not a real tier, is ``"public"``.
    """
    try:
        tier = load_allowlist().get(user_id, "public")
    except Exception:  # noqa: BLE001 - runs on every message; when in doubt, public
        return "public"
    return tier if tier in TIERS else "public"  # type: ignore[return-value]


__all__ = ["resolve", "load_allowlist", "ALLOWLIST_PATH", "OWNER", "INTERFACE", "STATUS"]
