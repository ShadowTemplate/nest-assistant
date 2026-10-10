# Chunking strategy (INGEST, W1-1.2)

Implemented in `src/nest_assistant/ingest/__init__.py`. Contains no Nest text.

## What a chunk is

One section of a document, or one answer of the residents' Q&A guides, packed with
its neighbours up to about **900 characters** (hard ceiling about 1400). The
section title is both stored in `Chunk.section` and repeated as the first line of
`text`, so a chunk still makes sense when it is read alone.

## Why structure-aware, not a fixed window

The corpus is small (7 documents, about 110 chunks) and most of it is organised
for people: numbered Bando clauses, and a guide made of short question-and-answer
pairs. A fixed window cuts through those units: a price table loses its header, an
answer is separated from its question. Splitting on structure keeps each fact next
to the words that say what it is about, which is what retrieval and citation need.
A fixed window would also give section-less citations.

No overlap. Overlap duplicates text, so one fact would be retrievable under two
ids, and "which chunk does the answer cite" stops having one answer.

The fixed-window comparison (task W1-1.3) has not been run. The numbers that would
justify this choice over a window belong there, not here.

## Pipeline

1. **Manifest gate.** `manifest.yaml` next to the documents gives tier and language.
   No entry means not ingested, and a warning names the file. No manifest at all
   raises. There is no default tier.
2. **Extract.** PDF text from `pypdf`; Markdown and text as they are.
3. **Clean.** Remove form feeds, page numbers, "back to index" links, and any line
   repeated on at least half the pages (running headers). Rejoin words hyphenated
   across lines and reflow wrapped prose; short lines (tables, lists) keep their
   line breaks. Pages that are only labels (maps, floor plans, covers) are dropped
   and logged at INFO; a page with schedule dates is kept.
4. **Order.** For single-column PDF pages, lines are put back in on-page order
   (drawing order can place a table after the next heading), and the page title is
   moved to the top.
5. **Split** on headings: Markdown `#`, numbered clauses (`1. ADMISSIONS`,
   `a. Sub-clause`), and ALL-CAPS titles followed by prose. Questions in capitals
   start a new unit. Then pack units to the target size.

## Ids

`<filename>#<n>`, where n counts chunks within that document in order. Re-running
over an unchanged file gives the same ids. **Editing a document can renumber
everything after the edit**, so ids are stable across runs, not across revisions.
If citations must survive revisions, the id would need to hash the content, and
that is a decision for the coordinators.

## Known weaknesses

- Checklist glyphs in the residents' guide come out as a stray `D` before items.
- Tables become one line per row, without column structure.
- Multi-column brochure pages are read column by column in PDF order, which is
  mostly right but not guaranteed.
- A few chunk sections are slightly off where a page title is a sentence fragment.
- Scanned (image-only) PDFs produce no text; they are reported, not OCR'd.
- `.docx` is supported in code but has not been exercised on a real file.
