"""Shared test setup.

**Tests never call a paid model.** Everyone runs ``make check`` before every
push, and several tests ask the pipeline questions — a full eval run among them.
With a team key in ``.env`` that would be ~45 model calls per run, billed to the
team, for thirty people, all day. So every test runs with the key blanked: the
pipeline then refuses instead of answering, which is exactly the offline
behaviour the tests check.

Measuring answer quality against the real model is what ``make eval`` is for.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_paid_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty value, not a deleted one: llm.load_dotenv() only fills variables
    # that are unset, so "" also stops it reading the real key back from .env.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
