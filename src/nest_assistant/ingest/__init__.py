"""TEAM 1 — INGEST · *documents in, clean text out*

You own one function::

    build_chunks(src: Path) -> list[Chunk]

Everybody downstream — INDEX, ANSWER, EVAL — receives whatever you return here
and nothing else. If a tier is wrong in your output, it is wrong in the whole
system, and no amount of prompting downstream will fix it.

Your tasks
----------
W1-1.1  Data inventory        -> data/manifest.yaml + data/INVENTORY.md
W1-1.2  Ingestion pipeline    -> this file, for real
W1-1.3  Chunking comparison   -> droppable

Stuck for 15 minutes?
---------------------
Read ``fixtures/manifest.yaml`` and ``tests/test_ingest.py``. The test says
exactly what "working" means. If the question is about what tier a document
should be, that is a policy question — take it to the PM coordinators, not to a
text editor.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..config import corpus_dir
from ..schema import TIERS, Chunk

OWNER = "TEAM 1 — INGEST"
INTERFACE = "ingest.build_chunks(src: Path) -> list[Chunk]"
STATUS = "real"  # `make board` reads this.

log = logging.getLogger(__name__)

TARGET_CHARS = 900
"""Pack neighbouring units of one section up to about this size."""
MAX_CHARS = 1400
"""A single unit longer than this is split on lines, then sentences."""

# Files that live next to the documents but are not documents.
_NOT_DOCUMENTS = {
    "manifest.yaml",
    "INVENTORY.md",
    "README.md",
    "allowlist.json",
    "bot_testers.json",
    ".gitkeep",
}
_SUPPORTED = {".pdf", ".md", ".txt", ".docx"}


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Entry:
    filename: str
    tier: str
    lang: str


_LANG = re.compile(r"^[a-z]{2}$")


def _load_manifest(src: Path) -> dict[str, _Entry]:
    """Read ``src/manifest.yaml``. Without one nothing can be ingested."""
    path = src / "manifest.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Without a manifest there are no tiers, and a document "
            "with no tier is not ingested."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("documents"), list):
        raise ValueError(f"{path}: expected a top-level 'documents:' list")
    entries: dict[str, _Entry] = {}
    problems: list[str] = []
    for item in raw["documents"]:
        if not isinstance(item, dict):
            problems.append(f"entry is not a mapping: {item!r}")
            continue
        name, tier, lang = item.get("filename"), item.get("tier"), item.get("lang")
        if not isinstance(name, str) or not name:
            problems.append(f"entry without a filename: {item!r}")
        elif tier not in TIERS:
            problems.append(f"{name}: tier={tier!r}, expected one of {list(TIERS)}")
        elif not isinstance(lang, str) or not _LANG.match(lang):
            # YAML reads an unquoted `no` as False, so a Norwegian entry needs quotes.
            problems.append(f"{name}: lang={lang!r}, expected a two-letter code like 'it'")
        elif name in entries:
            problems.append(f"{name} appears twice")
        else:
            entries[name] = _Entry(name, tier, lang)
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))
    return entries


def _documents(src: Path) -> list[Path]:
    return [
        p
        for p in sorted(src.rglob("*"))
        if p.is_file()
        and p.name not in _NOT_DOCUMENTS
        and not any(part.startswith(".") for part in p.relative_to(src).parts)
    ]


def _check_unique(documents: list[Path], manifest: dict[str, _Entry]) -> None:
    """Two listed files with one name would share ids. Unlisted files are never ingested."""
    counts = Counter(p.name for p in documents if p.name in manifest)
    dupes = {n for n, c in counts.items() if c > 1}
    if dupes:
        raise ValueError(f"same filename in two folders, citations would collide: {sorted(dupes)}")


# ---------------------------------------------------------------------------
# Extraction and cleaning
# ---------------------------------------------------------------------------
_Layout = Callable[[], str]
"""Layout text of one page, computed on first call: it is slow, and not every page needs it."""


@contextmanager
def _quiet_pypdf() -> Iterator[None]:
    """Silence pypdf for the duration of one document, then put the level back.

    Layout mode warns once per rotated label on every map page; it is noise. The
    level is restored so a corrupt or encrypted PDF elsewhere in the process is
    still reported.
    """
    logger = logging.getLogger("pypdf")
    before = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(before)


def _no_layout() -> str:
    return ""


def _read_pages(path: Path) -> list[tuple[str, _Layout]]:
    """``(text, layout)`` per page; ``layout()`` gives layout text, PDFs only.

    Plain extraction keeps columns apart but can emit a page title after the page
    body; layout extraction keeps the title on top but interleaves columns. We
    read with the first and use the second only to put the title back. Call this
    and consume the pages inside ``_quiet_pypdf()``.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return [
            (
                page.extract_text() or "",
                lambda page=page: page.extract_text(extraction_mode="layout") or "",
            )
            for page in PdfReader(path).pages
        ]
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table

        lines: list[str] = []
        for block in Document(path).iter_inner_content():  # paragraphs and tables, in order
            if isinstance(block, Table):
                for row in block.rows:
                    cells: list[str] = []
                    seen: list[object] = []
                    for cell in row.cells:
                        # A merged cell is returned once per column it spans. Compare the
                        # underlying element, not the text: "8.250 | 8.250" is two values.
                        if any(cell._tc is tc for tc in seen):
                            continue
                        seen.append(cell._tc)
                        if cell.text.strip():
                            cells.append(cell.text.strip())
                    lines.append(" | ".join(cells))
            else:
                lines.append(block.text)
        return [("\n".join(lines), _no_layout)]
    # utf-8-sig: a BOM left by a Windows editor would hide the first "# " heading.
    return [(path.read_text(encoding="utf-8-sig"), _no_layout)]


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


_NAV = re.compile(r"^<?\s*torna all.indice\s*$", re.I)
_PAGE_NO = re.compile(r"^(pag(ina|e)?\.?\s*)?\d{1,3}(\s*(/|di|of)\s*\d{1,3})?$", re.I)
_BARE_NUMBER = re.compile(r"^\d{1,3}$")


def _strip_page_number(page: list[str], number: int) -> list[str]:
    """Drop a page number from the first or last line of a PDF page, and only there.

    A number in the middle of a page is a value (``Singola`` / ``450``). At the
    edge it is a page number if it is spelled like one (``pag. 3``, ``3/9``) or,
    when it is a bare number, close to the page's position in the file.
    """

    def is_page_no(ln: str) -> bool:
        if not _PAGE_NO.match(ln):
            return False
        return not _BARE_NUMBER.match(ln) or abs(int(ln) - number) <= 5

    if page and is_page_no(page[-1]):
        page = page[:-1]
    if page and is_page_no(page[0]):
        page = page[1:]
    return page


_DATES = re.compile(
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)",
    re.I,
)
_DAY_OR_MONTH = re.compile(
    r"\b(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica|gennaio|febbraio|marzo|aprile|"
    r"maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|january|february|march|april|june|july|august|"
    r"september|october|november|december)\b",
    re.I,
)
_PRICE_OR_TIME = re.compile(r"[€$£]|\b(euro|eur)\b|\b\d{1,2}[:.]\d{2}\b", re.I)


def _is_prose(line: str) -> bool:
    """A statement, not a label: a sentence, a ``Key: value`` line, or a day or month."""
    if _is_upper(line):
        return False
    return len(line.split()) >= 4 or bool(re.search(r"\w: \S", line) or _DAY_OR_MONTH.search(line))


def _is_label_page(lines: list[str]) -> bool:
    """Cover, map, floor plan, index of icons: short labels and almost no prose.

    A page with a schedule (date ranges) is kept even if it looks like labels,
    because that is the infographic with the weekend dates. So is any page with a
    price or an opening time: a table of rates has short lines too, and dropping
    it would silently delete the facts people ask about.
    """
    if sum(bool(_DATES.search(ln)) for ln in lines) >= 2:
        return False
    if any(_PRICE_OR_TIME.search(ln) for ln in lines):
        return False
    if len(lines) < 3:
        return not any(_is_prose(ln) for ln in lines)
    mean = sum(map(len, lines)) / len(lines)
    return mean < 15 and sum(len(ln) >= 50 for ln in lines) < 3


def _lines(text: str) -> list[str]:
    return [n for n in (_norm(ln) for ln in text.replace("\x0c", "\n").splitlines()) if n]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _is_multicolumn(layout: str) -> bool:
    """Two or more lines with two long text runs side by side."""
    side_by_side = 0
    for ln in layout.splitlines():
        runs = [r for r in re.split(r" {5,}", ln.strip()) if len(r) >= 25]
        side_by_side += len(runs) >= 2
    return side_by_side >= 2


def _in_layout_order(page: list[str], layout: str) -> list[str]:
    """Reorder a single-column page's lines the way they sit on the page.

    Plain extraction follows the PDF's drawing order, so a table drawn last
    lands after the next section's heading. Layout extraction follows the
    page. Lines are matched to it with whitespace removed (layout letter-spaces
    display type); a line that cannot be placed stays with the line before it.
    """
    if not layout or _is_multicolumn(layout):
        return page
    flat = _squash(layout)
    keys: list[int] = []
    used: set[int] = set()
    last = 0
    for ln in page:
        sq = _squash(ln)
        found = flat.find(sq) if len(sq) >= 6 else -1
        while found in used:  # a repeated line takes the next occurrence, not the first again
            found = flat.find(sq, found + 1)
        if found >= 0:
            used.add(found)
        last = found if found >= 0 else last
        keys.append(last)
    order = sorted(range(len(page)), key=lambda i: (keys[i], i))
    return [page[i] for i in order]


def _layout_title(page: list[str], layout: str) -> str | None:
    """The page line that layout extraction shows as the page's ALL-CAPS title.

    Layout mode letter-spaces display type (``SPAZ I COMUNI``), so lines are
    compared with whitespace removed, and a truncated layout line still matches.
    """

    for ln in _lines(layout)[:6]:
        if not _is_upper(ln) or len(_squash(ln)) < 3:
            continue
        for candidate in page:
            if (
                len(candidate) <= 45
                and _is_upper(candidate)
                and _squash(candidate).startswith(_squash(ln))
            ):
                return candidate
    return None


_EDGE = 3
"""Furniture sits in the first or last few lines of a page."""


def _clean_pages(
    pages: list[tuple[str, _Layout]], name: str = "", *, pdf: bool = False
) -> list[list[str]]:
    """Per page: normalised lines with furniture removed.

    Furniture is any line that, on at least half the pages, is among the first or
    last three lines (running headers, footers, the ``Guida / Salvastudente``
    banner), plus "back to index" links and form feeds. A label that merely repeats
    in the body of a table (``Incluso``) is not at the edge and stays. Repeated
    lines only count in documents of three or more pages, so a short text file can
    never lose a line to that rule. Removed lines are logged. Page numbers are
    only removed from PDFs, and only from the first or last line of a page:
    elsewhere a line that is just ``450`` is a value, and in Markdown or text a
    line that is just ``12`` or ``1/2`` is content.
    """
    cleaned = [_lines(text) for text, _ in pages]
    if len(cleaned) >= 3:
        counts: dict[str, int] = {}
        for page in cleaned:
            for ln in set(page[:_EDGE] + page[-_EDGE:]):
                counts[ln] = counts.get(ln, 0) + 1
        furniture = {ln for ln, c in counts.items() if c >= len(cleaned) / 2}
        if furniture:
            log.info("%s: removed as running header/footer: %s", name, sorted(furniture))
    else:
        furniture = set()

    result: list[list[str]] = []
    for number, (page, (_, layout_of)) in enumerate(zip(cleaned, pages, strict=True), start=1):
        page = [
            ln
            for k, ln in enumerate(page)
            if not (ln in furniture and (k < _EDGE or k >= len(page) - _EDGE))
            and not _NAV.match(ln)
        ]
        if pdf:
            page = _strip_page_number(page, number)
        if pdf and _is_label_page(page):
            log.warning(
                "%s p.%d skipped as labels, not prose: check it held no facts", name, number
            )
            continue
        layout = layout_of()
        page = _in_layout_order(page, layout)
        if title := _layout_title(page, layout):
            page.remove(title)
            page.insert(0, title)
        result.append(page)
    return result


# ---------------------------------------------------------------------------
# Structure: headings, then units
# ---------------------------------------------------------------------------
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_TOP_HEADING = re.compile(r"^\d{1,2}\.\s+[A-ZÀ-Ý][A-ZÀ-Ý0-9 '’&/,-]{2,}$")
_SUB_HEADING = re.compile(r"^[a-z]\.\s+[A-ZÀ-Ý][^.?!]{2,50}$")
_BULLET = re.compile(r"^(•|\*|-|–|\d{1,2}[.)]|[a-z]\.)\s+")
_LIST_ITEM = re.compile(r"^[a-z]\.\s")


def _is_upper(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.85


def _is_question(line: str) -> bool:
    """The residents' guide is Q&A: ``COME FUNZIONA LA LAVANDERIA?`` starts an answer."""
    return line.endswith("?") and _is_upper(line)


_CAPS = 0
"""Level of an ALL-CAPS heading: outside the numbered/Markdown levels, so ``###`` is not one."""


def _heading(line: str, following: str = "") -> tuple[int, str] | None:
    """``(level, title)`` if the line is a section heading, else None.

    An ALL-CAPS line only counts when prose follows it. In brochures and maps the
    same shape is a label (``HOUSE``, ``PROFESSIONALIZZANTI``) followed by more
    labels, and promoting those would shred the document into one-line sections.
    """
    if m := _MD_HEADING.match(line):
        return len(m.group(1)), m.group(2)
    if _TOP_HEADING.match(line):
        return 1, line
    # "a. Programma offerto" is a sub-clause when prose follows it; in a run of short
    # items ("a. Essere maggiorenni" / "b. Essere iscritti") it is a list entry.
    if _SUB_HEADING.match(line) and len(following) >= 50 and not _LIST_ITEM.match(following):
        return 2, line
    prose_follows = len(following) >= 50 or _is_question(following)
    if (
        line.count("(") == line.count(")")  # a wrapped "(vedi X)" is not a title
        and len(line) <= 45
        and _is_upper(line)
        and not line.endswith((".", "?", ":", ","))
        and prose_follows
    ):
        return _CAPS, line
    return None


_COMPOUND_HEADS = {"check", "self", "non", "ex", "e", "post", "pre", "anti", "co", "multi", "extra"}
"""Words that take a hyphen when a line ends on them: ``check-in``, ``self-service``."""


def _join(lines: list[str]) -> str:
    """Reflow wrapped prose; keep short lines (tables, lists) on their own line."""
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif re.search(r"\w-$", out) and ln[:1].islower():
            head = re.split(r"[\s-]", out[:-1])[-1].lower()
            # "magi-" + "strale" is one word; "check-" + "in" is a compound.
            out = out + ln if head in _COMPOUND_HEADS else out[:-1] + ln
        elif len(out.rsplit("\n", 1)[-1]) >= 60 and not out.endswith((".", ":", ";", "?", "!")):
            out += " " + ln
        else:
            out += "\n" + ln
    return out


@dataclass
class _Section:
    title: str | None
    units: list[str]


_QUESTION_OPENER = re.compile(
    r"^(COME|COSA|CHE|CHI|DOVE|QUANDO|QUANTO|QUANTI|QUANTE|QUALE|QUALI|PERCH[ÉE]|POSSO|POSSONO|"
    r"DEVO|DEVONO|SI PU[ÒO]|C[’']?[ÈE]|CI SONO|[ÈE] POSSIBILE|[ÈE]|SONO|HO|HA|WHAT|WHERE|WHEN|"
    r"WHO|WHOM|WHICH|WHY|HOW|IS|ARE|CAN|COULD|DO|DOES|MUST|SHOULD|WILL|MAY|HAS|HAVE)\b",
    re.I,
)


def _rejoin_questions(lines: list[str]) -> list[str]:
    """A long ALL-CAPS question wraps onto two lines; put it back on one.

    Only a head that opens like a question is joined (``COME``, ``WHERE``, ``C'È``
    ...): a long ALL-CAPS notice just above a question is a title, not half of it.
    A question that opens with some other word is left as two lines, which is the
    safer mistake.
    """
    out: list[str] = []
    for ln in lines:
        wrapped = (
            out
            and _is_question(ln)
            and _is_upper(out[-1])
            and bool(_QUESTION_OPENER.match(out[-1]))
            and len(out[-1]) > 45  # shorter is a heading, not the first half of a question
            and not out[-1].endswith(("?", ".", ":"))
        )
        if wrapped:
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return out


def _sections(lines: list[str]) -> list[_Section]:
    """Split a document into sections, and each section into small units."""
    sections: list[_Section] = []
    path: list[str] = []
    cur: list[str] = []
    units: list[str] = []

    def flush_unit() -> None:
        nonlocal cur
        if cur:
            units.append(_join(cur))
            cur = []

    def flush_section(title: str | None) -> None:
        nonlocal units
        flush_unit()
        if units:
            sections.append(_Section(title, units))
        units = []

    lines = _rejoin_questions(lines)
    title: str | None = None
    caps: str | None = None  # an ALL-CAPS heading sits under the numbered path, not inside another
    for i, ln in enumerate(lines):
        if h := _heading(ln, lines[i + 1] if i + 1 < len(lines) else ""):
            flush_section(title)
            level, text = h
            if level == _CAPS:
                caps = text
            else:
                path, caps = path[: level - 1] + [text], None
            title = " > ".join(path + ([caps] if caps else []))
        else:
            if _is_question(ln) or _BULLET.match(ln):  # a new unit starts here
                flush_unit()
            cur.append(ln)
    flush_section(title)
    return sections


_ABBREVIATION = re.compile(r"\b(art|artt|sig|sigg|dott|prof|es|cfr|pag|ca|n)\.$", re.I)


def _cut_at_spaces(text: str, size: int) -> list[str]:
    """Pieces of at most ``size`` characters; cut on a space, or hard if there is none."""
    out: list[str] = []
    while len(text) > size:
        cut = text.rfind(" ", 0, size + 1)
        cut = cut if cut > 0 else size
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


MAX_TITLE = 200
"""A heading path longer than this is a misdetected heading; keep its deepest part."""


def _short_title(title: str | None) -> str | None:
    if title is None or len(title) <= MAX_TITLE:
        return title
    return "…" + title[-(MAX_TITLE - 1) :].lstrip()


def _split_long(unit: str, reserve: int = 0) -> list[str]:
    """Split a unit longer than ``MAX_CHARS`` on lines and sentences.

    ``reserve`` is room kept for the section title that ``build_chunks`` puts in
    front. No piece is longer than ``MAX_CHARS - reserve``: a sentence that is
    itself too long is cut at a space, and text with no space at all is cut hard.
    """
    target, limit = TARGET_CHARS - reserve, MAX_CHARS - reserve
    if len(unit) <= limit:
        return [unit]
    # Zero-width split points, so the space after a sentence stays with the next one.
    parts: list[str] = []
    for part in re.split(r"(?<=\n)|(?<=[.!?;])(?= )", unit):
        if parts and _ABBREVIATION.search(parts[-1].rstrip()):
            parts[-1] += part  # "Art." / "sig." is not the end of a sentence
        else:
            parts.append(part)
    pieces: list[str] = []
    cur = ""

    def cut(p: str) -> list[str]:
        # _cut_at_spaces strips its pieces; put the separator back so a piece
        # appended to ``cur`` does not glue onto the previous word.
        if len(p) <= limit:
            return [p]
        lead = p[: len(p) - len(p.lstrip())]
        return [(lead if k == 0 else " ") + q for k, q in enumerate(_cut_at_spaces(p, target))]

    for part in (q for p in parts for q in cut(p)):
        if cur and len(cur) + len(part) > target:
            pieces.append(cur.strip())
            cur = ""
        cur += part if cur else part.lstrip()
    if cur.strip():
        pieces.append(cur.strip())
    return pieces


def _pack(units: list[str], reserve: int = 0) -> list[str]:
    """Merge neighbouring units until a chunk reaches ``TARGET_CHARS - reserve``."""
    packed: list[str] = []
    cur = ""
    for unit in (p for u in units for p in _split_long(u, reserve)):
        if cur and len(cur) + len(unit) + 1 > TARGET_CHARS - reserve:
            packed.append(cur)
            cur = ""
        cur = f"{cur}\n{unit}" if cur else unit
    if cur:
        packed.append(cur)
    return packed


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------
def build_chunks(src: Path | None = None) -> list[Chunk]:
    """Read every document under ``src`` and return retrievable, citable chunks.

    Contract you must satisfy:

    * Every returned :class:`~nest_assistant.schema.Chunk` has a **stable** id.
      Re-running over an unchanged document produces the same ids, because
      citations made yesterday must still point at the right text today.
    * ``tier`` is inherited from ``manifest.yaml``. A document with no manifest
      entry is **not** ingested as ``public`` — it is not ingested at all, and it
      is reported. Defaulting to public is how a private document leaks.
    * ``source`` is the filename a human would name if they cited it by hand.
    * ``text`` is clean enough to read aloud: no page furniture, no repeated
      headers, no ``\\x0c``.
    * Chunks are small enough to retrieve precisely and large enough to make
      sense alone. Choosing that size is the interesting part of your job —
      write down what you chose and why.

    Args:
        src: directory of documents. Defaults to ``data/`` when it has content,
            otherwise the synthetic ``fixtures/``.

    Returns:
        Chunks, in document order.

    Strategy and rationale: ``docs/CHUNKING.md``.
    """
    src = Path(src) if src is not None else corpus_dir()
    manifest = _load_manifest(src)
    documents = _documents(src)
    _check_unique(documents, manifest)

    present = {p.name for p in documents}
    for path in documents:
        if path.name not in manifest:
            log.warning(
                "NOT INGESTED: %s has no manifest entry (no tier, so no ingestion)", path.name
            )
    for name in manifest:
        if name not in present:
            log.warning("manifest lists %s but the file is not in %s", name, src)

    chunks: list[Chunk] = []
    for path in documents:
        entry = manifest.get(path.name)
        if entry is None:
            continue
        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED:
            log.warning("NOT INGESTED: %s has unsupported format %s", path.name, path.suffix)
            continue
        with _quiet_pypdf():  # layout text is read lazily, inside _clean_pages
            pages = _clean_pages(_read_pages(path), path.name, pdf=suffix == ".pdf")
        lines = [ln for page in pages for ln in page]
        if suffix == ".txt":
            # In .txt files, "# ..." lines are comments for the people who maintain
            # the file (provenance, format notes), not text to answer from. In .md
            # the same line is a heading, so this is .txt only.
            lines = [ln for ln in lines if not ln.startswith("# ")]
        n = 0
        for section in _sections(lines):
            title = _short_title(section.title)
            reserve = len(title) + 1 if title else 0  # the title is prepended, so it counts
            for text in _pack(section.units, reserve):
                n += 1
                body = f"{title}\n{text}" if title else text
                chunks.append(
                    Chunk(
                        id=f"{path.name}#{n}",
                        text=body,
                        source=path.name,
                        tier=entry.tier,  # type: ignore[arg-type]
                        lang=entry.lang,
                        section=title,
                    )
                )
        if n == 0:
            log.warning("%s produced no text (scanned images?)", path.name)
    return chunks


__all__ = ["build_chunks", "OWNER", "INTERFACE", "STATUS"]
