"""The contracts.

Everything in this repository is built around the three types below. They are
agreed before the workshop starts and they do **not** change during the day
without the PM coordinators agreeing and telling every team.

If you find yourself wanting to add a field here, that is a conversation, not a
commit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

Tier = Literal["public", "resident", "staff"]
"""Who is asking. Ordered, ascending privilege.

- ``public``   — parents, prospective students, anyone at all
- ``resident`` — people who live at Nest
- ``staff``    — the secretariat and management

The same question gets a different *correct* answer depending on the tier of the
person asking. That is the spine of this project, not a detail.
"""

TIERS: tuple[Tier, ...] = ("public", "resident", "staff")

_TIER_RANK: dict[str, int] = {tier: rank for rank, tier in enumerate(TIERS)}


def tier_rank(tier: str) -> int:
    """Numeric privilege level of a tier. Higher means more privileged."""
    try:
        return _TIER_RANK[tier]
    except KeyError:
        raise ValueError(f"unknown tier: {tier!r} (expected one of {TIERS})") from None


def tier_allows(caller: str, required: str) -> bool:
    """True if a caller at tier ``caller`` may see content marked ``required``.

    This is the single function that decides who sees what. Use it; do not
    re-implement the comparison with ``>=`` on strings, because ``"public" >
    "resident"`` is True in Python and that is exactly the kind of bug that
    leaks a document.
    """
    return tier_rank(caller) >= tier_rank(required)


# ---------------------------------------------------------------------------
# Chunk — a retrievable piece of a document
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A piece of a Nest document, small enough to retrieve and cite.

    Produced by INGEST, stored and searched by INDEX, read by ANSWER, cited back
    to the user by CHAT.
    """

    id: str
    """Stable identifier, e.g. ``"regolamento.pdf#12"``.

    Stable means: re-running ingestion over an unchanged document produces the
    same id. Citations are worthless if the id moves.
    """

    text: str
    """The text itself. This is what the model is allowed to answer from."""

    source: str
    """Document filename, shown to the user as the citation."""

    tier: Tier
    """The *minimum* tier allowed to see this chunk."""

    lang: str
    """``"it"`` or ``"en"``."""

    section: str | None = None
    """Heading or section title, if the document has one. Helps the model cite
    precisely and helps a human check the citation."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Chunk:
        return cls(
            id=raw["id"],
            text=raw["text"],
            source=raw["source"],
            tier=raw["tier"],
            lang=raw["lang"],
            section=raw.get("section"),
        )


# ---------------------------------------------------------------------------
# Answer — what the assistant says back
# ---------------------------------------------------------------------------


@dataclass
class Answer:
    """One reply from the assistant."""

    text: str
    """What the user reads. Italian by default."""

    citations: list[str] = field(default_factory=list)
    """Chunk ids the answer is grounded in. An answer with no citations and
    ``refused=False`` is a red flag: it means the model spoke from memory."""

    confidence: float = 0.0
    """0..1. What it means is ANSWER's decision to define and EVAL's to check."""

    refused: bool = False
    """True when the assistant declined: "non lo so, chiedi in segreteria".

    A correct refusal is a success, not a failure. Measured as such by EVAL.
    """

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Scorecard — what EVAL produces
# ---------------------------------------------------------------------------


@dataclass
class Scorecard:
    """The number the whole project is judged on, and its parts.

    Written to a dated file so that March 2027 can compare itself with
    October 2026.
    """

    n_questions: int = 0
    retrieval_hit_rate: float = 0.0
    """Fraction of questions where at least one expected source was retrieved."""

    answer_correctness: float = 0.0
    """Fraction of answerable questions answered correctly."""

    refusal_precision: float = 0.0
    """Of the answers that were refusals, how many should have been."""

    refusal_recall: float = 0.0
    """Of the questions that should have been refused, how many were."""

    tier_leaks: int = 0
    """Chunks returned above the asker's tier. **Must be zero.** Any other
    number on this line makes every other number on the card irrelevant."""

    notes: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        """One screen, readable from the back of the room at 16:50."""
        leak_mark = "OK" if self.tier_leaks == 0 else "!! FAIL !!"
        return "\n".join(
            [
                "+----------------------------------------------+",
                "|  NEST ASSISTANT — SCORECARD                  |",
                "+----------------------------------------------+",
                f"  questions             {self.n_questions:>6}",
                f"  retrieval hit rate    {self.retrieval_hit_rate:>6.0%}",
                f"  answer correctness    {self.answer_correctness:>6.0%}",
                f"  refusal precision     {self.refusal_precision:>6.0%}",
                f"  refusal recall        {self.refusal_recall:>6.0%}",
                f"  tier leaks            {self.tier_leaks:>6}  {leak_mark}",
                "+----------------------------------------------+",
                f"  {self.notes}" if self.notes else "",
            ]
        ).rstrip()


# ---------------------------------------------------------------------------
# The pipeline protocol — what EVAL is handed
# ---------------------------------------------------------------------------


class PipelineProtocol(Protocol):
    """Anything that can answer a question on behalf of a given tier.

    ``evaluate.run()`` takes one of these. The real pipeline is in
    ``nest_assistant.pipeline``; a test can pass a fake with the same shape.
    """

    def ask(self, question: str, tier: Tier = "public") -> Answer: ...
