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
from ..schema import TIERS, Answer, Chunk, Tier, tier_rank

OWNER = "TEAM 3 — ANSWER"
INTERFACE = "answer.generate(q: str, chunks: list[Chunk], lang: str) -> Answer"
STATUS = "real"  # `make board` reads this.

REFUSAL_MARKER = "NON_TROVATO"
"""What the model writes when the documents do not answer. Matched, never shown."""

_CITATION_RE = re.compile(r"\s*\[([^\[\]]+#[^\[\]]+)\]")

_GAP_NEGATION_RE = re.compile(
    r"\b(?:non|nessun\w*|parzial\w*|not|no|only\s+partial)\b|n't\b", re.IGNORECASE
)
_GAP_SUBJECT_RE = re.compile(
    r"\b(?:document[oi]|documents?|fonti?|contesto|informazion\w*|dettagl\w*|indicat\w*|specificat\w*"
    r"|menzionat\w*|riportat\w*|descritt\w*|trovat[oaie]|trovare"
    r"|sources?|context|information|details?|specif\w*|mention\w*|stated?)\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^.!?\n]+")


def admits_gap(text: str) -> bool:
    """True if a sentence of ``text`` says the documents do not hold what was asked.

    "I documenti non specificano il costo", "non è indicato alcun prezzo",
    "dai documenti emerge solo una descrizione parziale": the model knows the
    answer is not there and answered anyway. A negation alone is not enough —
    "non sono disponibili camere triple" is a complete answer — so the same
    sentence must also be *about the information*: documents, details, what is
    indicated or mentioned. Italian and English behave the same way.

    A heuristic over phrasings, not understanding: it misses a gap the model
    words differently, and it would flag "non è indicato per soggiorni brevi".
    Both cases are in the tests.
    """
    return any(
        _GAP_NEGATION_RE.search(sentence) and _GAP_SUBJECT_RE.search(sentence)
        for sentence in _SENTENCE_RE.findall(text)
    )


REFUSAL_IT = (
    "Non ho trovato questa informazione nei documenti di Nest. "
    "Per essere sicuro, scrivi alla segreteria."
)
"""The refusal message. Parents will read this. Write it with care — it is the
sentence that decides whether "I don't know" sounds trustworthy or broken."""


CONFIDENCE_ONE_DOCUMENT = 0.6
CONFIDENCE_CORROBORATED = 0.8
"""``Answer.confidence`` has exactly three values, and they are levels, not
probabilities: 0.0 refused; 0.6 answered from one document; 0.8 answered from
two or more documents that the model cited together. Nothing here was
calibrated against outcomes, so do not threshold on "0.7" anywhere downstream:
the refusal decision is already made by :func:`generate`, and ``refused`` is the
field to read."""


def estimate_confidence(cited: list[str]) -> float:
    """Confidence level of an answer that passed every refusal check.

    Counts distinct *documents*, not chunk ids: two chunks of the same PDF are
    one witness. Retrieval scores are not used: with the e5 model every question
    scores 0.76-0.89, answerable or not.
    """
    documents = {cid.rsplit("#", 1)[0] for cid in cited}
    return CONFIDENCE_CORROBORATED if len(documents) >= 2 else CONFIDENCE_ONE_DOCUMENT


TIER_LABEL_IT = {"public": "pubblico", "resident": "residente", "staff": "staff"}
"""How a tier is named in the footer."""


def format_footer(confidence: float, chunks: list[Chunk], user_tier: Tier | None = None) -> str:
    """Footer line: the confidence score, the asker's tier and the tier requested.

    The tier requested is the highest tier among the cited chunks, i.e. the
    lowest tier of asker that could have been given this answer. The asker's own
    tier is shown only when the caller knows it.
    """
    tier = max((c.tier for c in chunks), key=tier_rank, default=TIERS[0])
    parts = [f"Affidabilità: {confidence:.0%}"]
    if user_tier is not None:
        parts.append(f"Il tuo livello: {TIER_LABEL_IT.get(user_tier, user_tier)}")
    parts.append(f"Livello richiesto: {TIER_LABEL_IT.get(tier, tier)}")
    return f"__{' · '.join(parts)}__"


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
def generate(
    q: str, chunks: list[Chunk], lang: str = DEFAULT_LANG, user_tier: Tier | None = None
) -> Answer:
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

    ``user_tier`` is the asker's tier; when given, the footer shows it.

    Refusal is decided here, by rules, in this order: no chunks; model
    unreachable; the model wrote ``NON_TROVATO``; no valid citation (it spoke
    from memory); an invented citation (it made at least part of it up); the
    text admits the documents do not hold the answer (:func:`admits_gap`). A
    partial answer is a refusal: "costa X, ma i documenti non dicono quando si
    paga" invites the parent to fill the gap with a guess.
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

    # No valid citation: it spoke from memory. An invented one: it made part of it up.
    if not cited or not text or len(cited) < len(found):
        return refusal
    if admits_gap(text):
        return refusal

    confidence = estimate_confidence(cited)
    cited_chunks = [c for c in chunks if c.id in cited]
    text = f"{text}\n\n{format_footer(confidence, cited_chunks, user_tier)}"
    return Answer(text=text, citations=cited, confidence=confidence, refused=False)


__all__ = [
    "generate",
    "load_system_prompt",
    "format_context",
    "estimate_confidence",
    "format_footer",
    "admits_gap",
    "REFUSAL_IT",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
