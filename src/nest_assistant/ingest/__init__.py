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
_NOT_DOCUMENTS = {"manifest.yaml", "INVENTORY.md", "README.md", "allowlist.json", ".gitkeep"}
_SUPPORTED = {".pdf", ".md", ".txt", ".docx"}


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Entry:
    filename: str
    tier: str
    lang: str


def _load_manifest(src: Path) -> dict[str, _Entry]:
    """Read ``src/manifest.yaml``. Without one nothing can be ingested."""
    path = src / "manifest.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Without a manifest there are no tiers, and a document "
            "with no tier is not ingested."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries: dict[str, _Entry] = {}
    for item in raw.get("documents", []):
        name, tier, lang = item.get("filename"), item.get("tier"), item.get("lang")
        if not name or tier not in TIERS or lang not in {"it", "en"}:
            raise ValueError(f"{path}: bad entry {name!r}: tier={tier!r} lang={lang!r}")
        if name in entries:
            raise ValueError(f"{path}: {name} appears twice")
        entries[name] = _Entry(name, tier, lang)
    return entries


def _documents(src: Path) -> list[Path]:
    found = [
        p
        for p in sorted(src.rglob("*"))
        if p.is_file() and p.name not in _NOT_DOCUMENTS and not p.name.startswith(".")
    ]
    names = [p.name for p in found]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"same filename in two folders, citations would collide: {sorted(dupes)}")
    return found


# ---------------------------------------------------------------------------
# Extraction and cleaning
# ---------------------------------------------------------------------------
def _read_pages(path: Path) -> list[tuple[str, str]]:
    """``(text, layout_text)`` per page. Layout text only exists for PDFs.

    Plain extraction keeps columns apart but can emit a page title after the page
    body; layout extraction keeps the title on top but interleaves columns. We
    read with the first and use the second only to put the title back.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        # Layout mode warns once per rotated label on every map page; it is noise.
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        return [
            (page.extract_text() or "", page.extract_text(extraction_mode="layout") or "")
            for page in PdfReader(path).pages
        ]
    if suffix == ".docx":
        from docx import Document

        return [("\n".join(p.text for p in Document(path).paragraphs), "")]
    return [(path.read_text(encoding="utf-8"), "")]


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


_NAV = re.compile(r"^<?\s*torna all.indice\s*$", re.I)
_PAGE_NO = re.compile(r"^(pag(ina|e)?\.?\s*)?\d{1,3}(\s*(/|di|of)\s*\d{1,3})?$", re.I)


_DATES = re.compile(
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)",
    re.I,
)


def _is_label_page(lines: list[str]) -> bool:
    """Cover, map, floor plan, index of icons: short labels and almost no prose.

    A page with a schedule (date ranges) is kept even if it looks like labels,
    because that is the infographic with the weekend dates.
    """
    if sum(bool(_DATES.search(ln)) for ln in lines) >= 2:
        return False
    if len(lines) < 3:
        return True
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
    last = 0
    for ln in page:
        sq = _squash(ln)
        found = flat.find(sq) if len(sq) >= 6 else -1
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


def _clean_pages(pages: list[tuple[str, str]], name: str = "") -> list[list[str]]:
    """Per page: normalised lines with furniture removed.

    Furniture is any line that repeats on at least half the pages (running
    headers, footers, the ``Guida / Salvastudente`` banner), page numbers,
    "back to index" links and form feeds. Only applied to multi-page documents,
    so a short text file can never lose a line to this rule.
    """
    cleaned = [_lines(text) for text, _ in pages]
    if len(cleaned) >= 3:
        counts: dict[str, int] = {}
        for page in cleaned:
            for ln in set(page):
                counts[ln] = counts.get(ln, 0) + 1
        furniture = {ln for ln, c in counts.items() if c >= len(cleaned) / 2}
    else:
        furniture = set()

    result: list[list[str]] = []
    for number, (page, (_, layout)) in enumerate(zip(cleaned, pages, strict=True), start=1):
        page = [
            ln
            for ln in page
            if ln not in furniture and not _NAV.match(ln) and not _PAGE_NO.match(ln)
        ]
        if layout and _is_label_page(page):  # layout text exists only for PDFs
            log.info("%s p.%d skipped: labels, not prose", name, number)
            continue
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
_BULLET = re.compile(r"^(•|\*|-|–|\d{1,2}[.)])\s+")


def _is_upper(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.85


def _is_question(line: str) -> bool:
    """The residents' guide is Q&A: ``COME FUNZIONA LA LAVANDERIA?`` starts an answer."""
    return line.endswith("?") and _is_upper(line)


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
    if _SUB_HEADING.match(line):
        return 2, line
    prose_follows = len(following) >= 50 or _is_question(following)
    if (
        line.count("(") == line.count(")")  # a wrapped "(vedi X)" is not a title
        and len(line) <= 45
        and _is_upper(line)
        and not line.endswith((".", "?", ":", ","))
        and prose_follows
    ):
        return 3, line
    return None


def _join(lines: list[str]) -> str:
    """Reflow wrapped prose; keep short lines (tables, lists) on their own line."""
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif re.search(r"\w-$", out) and ln[:1].islower():
            out = out[:-1] + ln  # "magi-" + "strale"
        elif len(out.rsplit("\n", 1)[-1]) >= 60 and not out.endswith((".", ":", ";", "?", "!")):
            out += " " + ln
        else:
            out += "\n" + ln
    return out


@dataclass
class _Section:
    title: str | None
    units: list[str]


def _rejoin_questions(lines: list[str]) -> list[str]:
    """A long ALL-CAPS question wraps onto two lines; put it back on one."""
    out: list[str] = []
    for ln in lines:
        wrapped = (
            out
            and _is_question(ln)
            and _is_upper(out[-1])
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
            if level == 3:
                caps = text
            else:
                path, caps = path[: level - 1] + [text], None
            title = " > ".join(path + ([caps] if caps else []))
        elif _is_question(ln) or _BULLET.match(ln) or ln == "":
            flush_unit()
            if ln:
                cur.append(ln)
        else:
            cur.append(ln)
    flush_section(title)
    return sections


def _split_long(unit: str) -> list[str]:
    if len(unit) <= MAX_CHARS:
        return [unit]
    pieces: list[str] = []
    cur = ""
    for part in re.split(r"(?<=\n)|(?<=[.!?;]) ", unit):
        if cur and len(cur) + len(part) > TARGET_CHARS:
            pieces.append(cur.strip())
            cur = ""
        cur += part
    if cur.strip():
        pieces.append(cur.strip())
    return pieces


def _pack(units: list[str]) -> list[str]:
    """Merge neighbouring units until a chunk reaches ``TARGET_CHARS``."""
    packed: list[str] = []
    cur = ""
    for unit in (p for u in units for p in _split_long(u)):
        if cur and len(cur) + len(unit) + 1 > TARGET_CHARS:
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
        if path.suffix.lower() not in _SUPPORTED:
            log.warning("NOT INGESTED: %s has unsupported format %s", path.name, path.suffix)
            continue
        pages = _clean_pages(_read_pages(path), path.name)
        lines = (
            [ln for page in pages for ln in page if not ln.startswith("# ")]
            if (path.suffix.lower() == ".txt")
            else [ln for page in pages for ln in page]
        )
        n = 0
        for section in _sections(lines):
            for text in _pack(section.units):
                n += 1
                body = f"{section.title}\n{text}" if section.title else text
                chunks.append(
                    Chunk(
                        id=f"{path.name}#{n}",
                        text=body,
                        source=path.name,
                        tier=entry.tier,  # type: ignore[arg-type]
                        lang=entry.lang,
                        section=section.title,
                    )
                )
        if n == 0:
            log.warning("%s produced no text (scanned images?)", path.name)
    return chunks


__all__ = ["build_chunks", "OWNER", "INTERFACE", "STATUS"]
