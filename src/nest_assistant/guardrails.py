"""TEAM 5 — EVAL · the last thing that runs before a user sees an answer.

Task W1-5.3. You break the system on purpose in ``eval/redteam.yaml``, then you
stop it from breaking, here.

This is the *second* line of defence, never the first. A guardrail that catches
a leaked staff chunk is a bug report for INDEX, not a fix. Say so out loud when
you find one.

Every rule that fires is logged and counted (see :func:`counts`). A guardrail
that fires is a finding: it goes in ``eval/FINDINGS.md``.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from .answer import REFUSAL_IT
from .config import PROMPTS_DIR
from .schema import Answer, Chunk, Tier, tier_allows

OWNER = "TEAM 5 — EVAL"
STATUS = "real"

log = logging.getLogger("nest.guardrails")

MAX_CHARS = 1200
"""A chat answer, not a document. Longer output is cut at a sentence boundary."""

SHINGLE_WORDS = 6
"""A run of this many consecutive words shared with a protected text counts as
repeating it."""

_FIRED: Counter[str] = Counter()
_EVENTS: list[dict[str, str]] = []


def counts() -> dict[str, int]:
    """How many times each rule has fired in this process."""
    return dict(_FIRED)


def events() -> list[dict[str, str]]:
    """Every firing since the last :func:`reset`: rule, tier and a text excerpt."""
    return list(_EVENTS)


def reset() -> None:
    """Clear the counters. Call it before a measured run."""
    _FIRED.clear()
    _EVENTS.clear()


def _fire(rule: str, tier: Tier, detail: str) -> None:
    _FIRED[rule] += 1
    _EVENTS.append({"rule": rule, "tier": tier, "detail": detail[:160]})
    log.warning("guardrail %s fired for tier=%s: %s", rule, tier, detail[:160])


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _shingles(text: str, n: int = SHINGLE_WORDS) -> set[tuple[str, ...]]:
    words = _words(text)
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _shares_text(answer_text: str, protected: str) -> bool:
    return bool(_shingles(answer_text) & _shingles(protected))


def _system_prompt() -> str:
    path = PROMPTS_DIR / "answer_system.it.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


# Output that shows the model has been talked out of its role. These phrases are
# not things Nest's documents say, so any match is suspicious.
_INJECTION = re.compile(
    r"ignor\w*\s+(?:tutte\s+)?(?:le\s+)?(?:istruzioni|regole)"
    r"|\[/?system\]"
    r"|modalit[àa]\s+(?:sviluppatore|developer|admin|dev)\b"
    r"|senza\s+(?:nessuna\s+|alcuna\s+)?(?:regola|regole|restrizioni|limiti)"
    r"|accesso\s+(?:completo|totale)\s+(?:concesso|garantito|attivato)"
    r"|(?:ora|adesso|da ora)\s+(?:sei|sono|siete)\s+(?:un\s+)?(?:staff|admin|amministratore)",
    re.IGNORECASE,
)

# Promises made in Nest's name. Fine if a cited document says it; a finding if not.
_PROMISE = re.compile(
    r"\bgarantisc\w+|\bgarantit[oaie]\b|\bti assicuro\b|\bvi assicuro\b"
    r"|\bassicuriamo\b|\bprometto\b|\bpromettiamo\b"
    r"|\bsicuramente\s+(?:avrai|avrete|ottien\w+|sarai|sarete)\b",
    re.IGNORECASE,
)

# Tone Nest would not use in its own voice.
_HOSTILE = re.compile(
    r"\bazion[ei]\s+legal\w*\b|\bti\s+(?:denunc|quereler)\w*|\bvi\s+(?:denunc|quereler)\w*"
    r"|\bfaremo\s+causa\b|\bci vedremo in tribunale\b",
    re.IGNORECASE,
)

_PHONE = re.compile(r"(?<!\d)(?:\+?39[\s.-]?)?3\d{2}[\s.-]?\d{6,7}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


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


def _refuse(rule: str, tier: Tier, detail: str) -> Answer:
    _fire(rule, tier, detail)
    return Answer(text=REFUSAL_IT, citations=[], confidence=0.0, refused=True)


def _truncate(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > MAX_CHARS // 2 else cut.rstrip()) + " …"


def apply(answer: Answer, chunks: list[Chunk], tier: Tier) -> Answer:
    """Last check before the answer leaves the building.

    Rules, in order. ``invented_citation``, ``hidden_citation`` and ``too_long``
    repair the answer; every other rule replaces it with the standard refusal.
    Each one that fires is counted and logged.

    1. ``invented_citation`` — a cited id that was never retrieved (repaired,
       and counted).
    2. ``hidden_citation`` — a cited id of a chunk the caller's tier may not
       see (repaired, and counted). Should never fire: the pipeline filters by
       tier before generating, so if it does, INDEX has a bug.
    3. ``hidden_chunk_text`` — the answer repeats text from a chunk the caller's
       tier may not see. Should never fire: if it does, INDEX has a bug.
    4. ``system_prompt_leak`` — the answer repeats the system prompt.
    5. ``injection_in_output`` — the answer agrees to drop its rules, adopts a
       new persona, or grants itself access.
    6. ``unsupported_promise`` — a commitment ("garantiamo", "ti assicuro")
       that no cited document contains.
    7. ``personal_data`` — a phone number or email that is in no retrieved
       chunk, for a non-staff caller.
    8. ``hostile_tone`` — legal threats or similar, in Nest's voice.
    9. ``uncited_answer`` — a non-refusal with no surviving citation: the model
       spoke from memory.
    10. ``too_long`` — cut at a sentence boundary (repaired).

    Known limits: the text rules are phrase-based (Italian only), so a reworded
    or translated attack can pass. Hidden-chunk and hidden-citation detection need
    the hidden chunk to be in ``chunks``; the pipeline passes only visible ones,
    so the real defence is INDEX's filter. See ``eval/FINDINGS.md``.
    """
    # Citations are checked against the chunks this tier may see, not against
    # everything that was passed in: a cite to a hidden chunk is as bad as an
    # invented one, and survives if the filter is skipped.
    visible = [c for c in chunks if tier_allows(tier, c.tier)]
    hidden_ids = {c.id for c in chunks} - {c.id for c in visible}
    before = list(answer.citations)
    answer = enforce_citations(answer, visible)
    dropped = [c for c in before if c not in answer.citations]
    invented = [c for c in dropped if c not in hidden_ids]
    hidden = [c for c in dropped if c in hidden_ids]
    if invented:
        _fire("invented_citation", tier, ", ".join(invented))
    if hidden:
        _fire("hidden_citation", tier, ", ".join(hidden))

    if answer.refused:
        return answer

    text = answer.text

    for chunk in chunks:
        if not tier_allows(tier, chunk.tier) and _shares_text(text, chunk.text):
            return _refuse("hidden_chunk_text", tier, f"repeats {chunk.id} ({chunk.tier})")

    if _shares_text(text, _system_prompt()):
        return _refuse("system_prompt_leak", tier, text)

    match = _INJECTION.search(text)
    if match:
        return _refuse("injection_in_output", tier, match.group(0))

    cited = [c for c in chunks if c.id in answer.citations]
    cited_text = " ".join(c.text for c in cited).lower()
    for match in _PROMISE.finditer(text):
        stem = match.group(0).lower()[:6]
        if stem not in cited_text:
            return _refuse("unsupported_promise", tier, match.group(0))

    if tier != "staff":
        known = " ".join(c.text for c in chunks)
        known_digits = _digits(known)
        for phone in _PHONE.findall(text):
            if _digits(phone) not in known_digits:
                return _refuse("personal_data", tier, phone)
        for email in _EMAIL.findall(text):
            if email.lower() not in known.lower():
                return _refuse("personal_data", tier, email)

    match = _HOSTILE.search(text)
    if match:
        return _refuse("hostile_tone", tier, match.group(0))

    if not answer.citations:
        return _refuse("uncited_answer", tier, text)

    if len(text) > MAX_CHARS:
        _fire("too_long", tier, f"{len(text)} chars")
        answer.text = _truncate(text)

    return answer


__all__ = [
    "apply",
    "enforce_citations",
    "counts",
    "events",
    "reset",
    "MAX_CHARS",
    "OWNER",
    "STATUS",
]
