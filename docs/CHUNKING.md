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
3. **Clean.** Remove form feeds, "back to index" links, and any line repeated on
   at least half the pages of a document of three or more pages (running headers).
   Page numbers (`12`, `1/2`, `pag. 3 di 9`) are removed from PDFs only; in `.md`
   and `.txt` such a line is content. In `.txt` files, lines starting with `# ` are
   maintainer comments (provenance, format notes) and are dropped; in `.md` the same
   line is a heading and is kept. Rejoin words hyphenated
   across lines and reflow wrapped prose; short lines (tables, lists) keep their
   line breaks. Pages that are only labels (maps, floor plans, covers) are dropped
   and logged at **WARNING**, so a wrongly dropped page is visible. A page with
   schedule dates, a currency symbol or an opening time is never dropped as labels.
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
- Blank lines are discarded on read, so paragraphs in `.md` files merge into one
  unit; headings and bullets still split them.
- The label-page rule is a heuristic. Read the WARNING lines after each ingest of
  new documents; a page of bare numbers (room codes, years) with no price or time
  can still be dropped.
- Scanned (image-only) PDFs produce no text; they are reported, not OCR'd.
- `.docx` is supported in code but has not been exercised on a real file.

## Checking the numbers above

CI cannot check "7 documents, about 110 chunks": it only sees the synthetic
fixtures. On a machine with the real `data/`:

```
make ingest        # writes build/chunks.jsonl, warnings name anything skipped
python -c "import json,collections; c=collections.Counter(json.loads(l)['source'] for l in open('build/chunks.jsonl')); print(len(c), sum(c.values())); print(c)"
```

Expect 7 sources and a total near 110. Also read the `skipped as labels` warnings.
Re-check after the documents change; if the counts drift a lot, update this file.
