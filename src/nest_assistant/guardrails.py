"""TEAM 5 — EVAL · the last thing that runs before a user sees an answer.

Task W1-5.3. You break the system on purpose in ``eval/redteam.yaml``, then you
stop it from breaking, here.

This is the *second* line of defence, never the first. A guardrail that catches
a leaked staff chunk is a bug report for INDEX, not a fix. Say so out loud when
you find one.
"""

from __future__ import annotations

from .schema import Answer, Chunk, Tier, tier_allows

OWNER = "TEAM 5 — EVAL"
STATUS = "stub"


def enforce_citations(answer: Answer, chunks: list[Chunk]) -> Answer:
    """Drop citations that do not correspond to a retrieved chunk.

    A model that cites ``regolamento.pdf#99`` when no such chunk was retrieved
    has invented a source, and an invented source is worse than none: it looks
    checkable and is not.
    """
    allowed = {c.id for c in chunks}
    kept = [cid for cid in answer.citations if cid in allowed]
    if len(kept) != len(answer.citations):
        answer.citations = kept
    return answer


# ---------------------------------------------------------------------------
# TEAM 5 — REPLACE ME (W1-5.3)
# ---------------------------------------------------------------------------
def apply(answer: Answer, chunks: list[Chunk], tier: Tier) -> Answer:
    """Last check before the answer leaves the building.

    Ideas worth trying, in roughly the order they will pay off:

    * Citation integrity (already here — read it, then improve it).
    * Refuse to repeat text from a chunk the caller was not allowed to see.
      Defence in depth: this should never fire. Count it if it does.
    * Detect prompt injection landing in the *output* — the assistant agreeing
      to "ignore previous instructions", changing persona, or promising things
      on Nest's behalf.
    * Length and tone limits, so a hostile prompt cannot turn the bot into a
      megaphone.

    What you must not do: silently swallow a problem. If a guardrail fires, that
    is a finding. Log it, count it, and write it up in your findings note.
    """
    answer = enforce_citations(answer, chunks)

    # Defence in depth. If this ever removes anything, INDEX has a bug — that is
    # a conversation with team 2, not a line of code here.
    visible = [c for c in chunks if tier_allows(tier, c.tier)]
    if len(visible) != len(chunks):
        answer = enforce_citations(answer, visible)

    return answer


__all__ = ["apply", "enforce_citations", "OWNER", "STATUS"]
