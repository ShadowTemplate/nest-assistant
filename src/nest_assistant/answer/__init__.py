"""TEAM 3 — ANSWER · *retrieved text in, trustworthy Italian out*

You own one function::

    generate(q: str, chunks: list[Chunk], lang: str) -> Answer

Your tasks
----------
W1-3.1  Grounded generation     -> a real answer, in Italian, with citations
W1-3.2  Refusal and abstention  -> **the most important task of the day**
W1-3.3  Answer quality pass     -> droppable

Two things that are not negotiable
----------------------------------
1. **The system prompt lives in ``prompts/answer_system.it.md``, not in a string
   in this file.** A prompt is logic. It gets reviewed, versioned, and blamed
   like any other logic. Edit the file; do not paste it into the code.
2. **Every claim in the answer comes from ``chunks``.** If the chunks do not
   contain the answer, the correct output is a refusal. A confidently wrong
   answer about a deposit refund costs Nest more than an unhelpful one.

Stuck for 15 minutes?
---------------------
Run ``make demo`` and read what the stub prints. Then read
``prompts/answer_system.it.md``. If the problem is that INDEX is giving you
rubbish chunks, that is a real finding — tell them, do not paper over it here.
"""

from __future__ import annotations

from ..config import DEFAULT_LANG, PROMPTS_DIR
from ..schema import Answer, Chunk

OWNER = "TEAM 3 — ANSWER"
INTERFACE = "answer.generate(q: str, chunks: list[Chunk], lang: str) -> Answer"
STATUS = "stub"  # flip to "real" when you replace the body below. `make board` reads this.

REFUSAL_IT = (
    "Non ho trovato questa informazione nei documenti di Nest. "
    "Per essere sicuro, scrivi alla segreteria."
)
"""The refusal message. Parents will read this. Write it with care — it is the
sentence that decides whether "I don't know" sounds trustworthy or broken."""


def load_system_prompt(lang: str = DEFAULT_LANG) -> str:
    """Read the system prompt from ``prompts/``. Falls back to Italian."""
    path = PROMPTS_DIR / f"answer_system.{lang}.md"
    if not path.exists():
        path = PROMPTS_DIR / "answer_system.it.md"
    return path.read_text(encoding="utf-8")


def format_context(chunks: list[Chunk]) -> str:
    """Lay the retrieved chunks out for the model, ids included.

    The ids are in the text on purpose: a model that cannot see an id cannot
    cite one.
    """
    return "\n\n".join(
        f"[{c.id}] (fonte: {c.source}"
        + (f", sezione: {c.section}" if c.section else "")
        + f")\n{c.text}"
        for c in chunks
    )


# ---------------------------------------------------------------------------
# TEAM 3 — REPLACE ME
# ---------------------------------------------------------------------------
def generate(q: str, chunks: list[Chunk], lang: str = DEFAULT_LANG) -> Answer:
    """Answer ``q`` using only ``chunks``, in ``lang``.

    Contract you must satisfy:

    * ``Answer.text`` is in ``lang`` (``"it"`` by default), reads like a person
      wrote it, and fits in a chat message.
    * ``Answer.citations`` contains only ids that are actually in ``chunks``.
      An id you invented is worse than no citation at all.
    * ``Answer.refused`` is True **and** ``text`` is a refusal when the chunks do
      not answer the question. Set ``confidence`` to something you can defend.
    * Empty ``chunks`` always produces a refusal. No exceptions, no guessing.
    * The function never raises. If the model is unreachable, refuse — the bot
      stays up and says something honest.

    Use :func:`~nest_assistant.llm.complete` to call the model, and
    :func:`load_system_prompt` to get your prompt. Both exist so that October's
    hosted model and October-2027's self-hosted one look identical from here.

    The stub below echoes what it *would* have used, so that CHAT, EVAL and
    INDEX all have a working pipeline before you have written anything.
    """
    if not chunks:
        return Answer(text=REFUSAL_IT, citations=[], confidence=0.0, refused=True)

    preview = "; ".join(f"{c.source}#{c.id}" for c in chunks[:3])
    return Answer(
        text=(
            f"(stub) Risponderei a «{q}» usando: {preview}. "
            "Sostituisci answer.generate() con una vera generazione."
        ),
        citations=[c.id for c in chunks],
        confidence=0.0,
        refused=False,
    )


__all__ = [
    "generate",
    "load_system_prompt",
    "format_context",
    "REFUSAL_IT",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
