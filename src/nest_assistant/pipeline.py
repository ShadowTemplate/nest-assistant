"""The whole assistant, in about thirty lines.

**Nobody owns this file.** It is the wiring between the six components, and it
changes only if the PM coordinators agree — because a change here affects every
team at once.

Read it. It is the shortest honest description of what we are building::

    question + who is asking
        -> index.search()      find the relevant text this person may see
        -> (tier guard)        defence in depth
        -> answer.generate()   turn that text into an Italian answer
        -> guardrails.apply()  last check before a human reads it
"""

from __future__ import annotations

from dataclasses import dataclass

from . import guardrails
from .answer import REFUSAL_IT, generate
from .config import DEFAULT_K, DEFAULT_LANG
from .index import search
from .schema import Answer, Chunk, Tier, tier_allows


@dataclass
class Pipeline:
    """One configured assistant. Cheap to build; build one per process."""

    k: int = DEFAULT_K
    lang: str = DEFAULT_LANG

    def retrieve(self, question: str, tier: Tier = "public") -> list[Chunk]:
        """Raw search results, exactly as INDEX returned them.

        Deliberately *not* filtered: EVAL measures tier leaks against this, and a
        leak you have cleaned up before measuring is a leak you will ship.
        """
        return search(question, tier, self.k)

    def ask(self, question: str, tier: Tier = "public") -> Answer:
        """Answer ``question`` on behalf of someone at ``tier``.

        Never raises. A broken component produces a refusal, not a stack trace in
        a resident's chat window.
        """
        try:
            retrieved = self.retrieve(question, tier)
        except Exception:  # noqa: BLE001 - a search failure must not kill the bot
            retrieved = []

        # Defence in depth: INDEX's stub does not filter by tier, and INDEX's real
        # implementation might have a bug. Two independent layers, both working.
        visible = [c for c in retrieved if tier_allows(tier, c.tier)]

        try:
            answer = generate(question, visible, self.lang)
        except Exception:  # noqa: BLE001 - same reason
            answer = Answer(text=REFUSAL_IT, citations=[], confidence=0.0, refused=True)

        return guardrails.apply(answer, visible, tier)


def ask(question: str, tier: Tier = "public", k: int = DEFAULT_K) -> Answer:
    """Convenience wrapper for one-off questions (``make demo``, tests, notebooks)."""
    return Pipeline(k=k).ask(question, tier)
