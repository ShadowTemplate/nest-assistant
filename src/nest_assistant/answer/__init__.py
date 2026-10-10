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

import re

from .. import llm
from ..config import DEFAULT_LANG, PROMPTS_DIR
from ..schema import Answer, Chunk

OWNER = "TEAM 3 — ANSWER"
INTERFACE = "answer.generate(q: str, chunks: list[Chunk], lang: str) -> Answer"
STATUS = "real"  # `make board` reads this.

REFUSAL_MARKER = "NON_TROVATO"
"""What the model writes when the documents do not answer. Matched, never shown."""

_CITATION_RE = re.compile(r"\s*\[([^\[\]]+#[^\[\]]+)\]")

_HEDGE_RE = re.compile(
    # Italian: "non specificano", "non è stato possibile trovare", "non sono presenti".
    # "non solo X ma anche Y" is not a hedge, hence the lookahead.
    r"\bnon\s+(?!solo\b)(?:\w+\s+){0,3}?"
    r"(?:dicono|dice|specific\w+|risult\w+|indic\w+|precis\w+|menzion\w+|riport\w+"
    r"|present\w+|disponibil\w+|trov\w+|possibile)"
    # English, for lang="en": "the documents do not specify".
    r"|\b(?:do(?:es)?\s+not|don't|doesn't|not)\s+(?:\w+\s+){0,2}?"
    r"(?:specify|state|mention|say|provide|indicate|contain|include)",
    re.IGNORECASE,
)
"""The model admits a gap inside an otherwise answered question. A heuristic over
a handful of phrasings, not a language model: it will miss some."""

REFUSAL_IT = (
    "Non ho trovato questa informazione nei documenti di Nest. "
    "Per essere sicuro, scrivi alla segreteria."
)
"""The refusal message. Parents will read this. Write it with care — it is the
sentence that decides whether "I don't know" sounds trustworthy or broken."""


def estimate_confidence(text: str, cited: list[str], invented: int) -> float:
    """How far to trust a non-refused answer, 0..1. A heuristic, not a probability.

    Retrieval scores cannot do this job: with the e5 model every question scores
    0.76-0.89, answerable or not. What we can see instead: how many distinct
    *documents* back the answer, whether the model cited ids it was never given,
    and whether it admits a gap in its own text.

    The score is ``0.6``, plus ``0.1`` for a second document, minus ``0.2`` for an
    invented id and ``0.2`` for an admitted gap: it lives in 0.2-0.7, so it is
    never 1.0 (nothing here is proof) and no clamp is needed. A refusal is 0.0.

    An answer that admits a gap is lowered, not refused: "the price is X; the
    documents do not say more about meals" is useful to a parent. Whether a
    partial answer should be a refusal is a product decision, not a scoring one.
    """
    documents = {cid.rsplit("#", 1)[0] for cid in cited}
    score = 0.6 + (0.1 if len(documents) >= 2 else 0.0)
    if invented:
        score -= 0.2
    if _HEDGE_RE.search(text):
        score -= 0.2
    return round(score, 2)


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

    W1-3.1: grounded generation. Refusal thresholds are W1-3.2.
    """
    refusal = Answer(text=REFUSAL_IT, citations=[], confidence=0.0, refused=True)
    if not chunks:
        return refusal

    prompt = f"## Documenti\n\n{format_context(chunks)}\n\n## Domanda\n\n{q}"
    try:
        raw = llm.complete(prompt, system=load_system_prompt(lang))
    except Exception:  # generate() never raises: an honest refusal keeps the bot up
        return refusal

    if not raw or REFUSAL_MARKER in raw:
        return refusal

    supplied = {c.id for c in chunks}
    found = list(dict.fromkeys(_CITATION_RE.findall(raw)))
    cited = [cid for cid in found if cid in supplied]
    text = _CITATION_RE.sub("", raw)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()

    # No valid citation means the model spoke from memory: treat it as a refusal.
    if not cited or not text:
        return refusal

    return Answer(
        text=text,
        citations=cited,
        confidence=estimate_confidence(text, cited, len(found) - len(cited)),
        refused=False,
    )


__all__ = [
    "generate",
    "load_system_prompt",
    "format_context",
    "estimate_confidence",
    "REFUSAL_IT",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
