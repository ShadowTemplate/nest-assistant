# Chunking strategy (INGEST, W1-1.2)

Implemented in `src/nest_assistant/ingest/__init__.py`. Contains no Nest text.

## What a chunk is

One section of a document, or one answer of the residents' Q&A guides, packed with
its neighbours up to about **900 characters**, counting the title (a title longer than 200 characters is cut to its deepest part; hard ceiling 1400:
a single unit that fits under it is kept whole, anything longer is cut on sentences,
then on spaces, then hard). The section title is both stored in `Chunk.section` and
repeated as the first line of `text`, so a chunk still makes sense when it is read
alone.

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

1. **Manifest gate.** `manifest.yaml` next to the documents gives tier and language
   (any two-letter code; quote `'no'`, which YAML reads as false). No entry means not
   ingested, and a warning names the file. No manifest at all raises, and so does a
   bad entry, with every bad entry listed in one error. There is no default tier.
   Two listed files with the same name in different folders raise (their ids would
   collide); unlisted duplicates are ignored.
2. **Extract.** PDF text from `pypdf`; Markdown and text as they are; `.docx`
   paragraphs and tables in document order (a table row becomes `cell | cell`; a
   merged cell appears once, equal values in separate cells both stay). PDF layout
   text, which is slow, is computed only for pages that survive cleaning.
3. **Clean.** Remove form feeds, "back to index" links, and any line that is among
   the first or last three lines of at least half the pages of a document of three or
   more pages (running headers and footers; a label repeated inside a table body
   stays). Removed lines are logged at INFO.
   Page numbers (`12`, `1/2`, `pag. 3 di 9`) are removed from PDFs only, and only when
   they are the first or last line of a page (a bare number must also be within 5 of
   the page's position in the file). A number in the middle of a page is a value, as
   in a price table. In `.md` and `.txt` such a line is content. In `.txt` files, lines starting with `# ` are
   maintainer comments (provenance, format notes) and are dropped; in `.md` the same
   line is a heading and is kept. Rejoin words hyphenated
   across lines and reflow wrapped prose; short lines (tables, lists) keep their
   line breaks. A hyphen at the end of a line is dropped (`magi-` `strale`) except
   after a few known compound heads (`check-` `in` stays `check-in`). Pages that are only labels (maps, floor plans, covers) are dropped
   and logged at **WARNING**, so a wrongly dropped page is visible. A page with
   schedule dates, a currency symbol, an opening time, a sentence of four or more
   words, a `Key: value` line, or a day or month name is never dropped as labels.
4. **Order.** For single-column PDF pages, lines are put back in on-page order
   (drawing order can place a table after the next heading), and the page title is
   moved to the top.
5. **Split** on headings: Markdown `#`, numbered clauses (`1. ADMISSIONS`,
   `a. Sub-clause`), and ALL-CAPS titles followed by prose. An `a. ...` line is a
   sub-clause only when prose follows it; in a run of short items (`a. Essere
   maggiorenni` / `b. Essere iscritti`) each is a list entry inside its section. Questions in capitals
   start a new unit. A question wrapped over two lines is rejoined only when it opens
   like a question (`COME`, `WHERE`, `C'È` ...); anything else stays as two lines. Then pack units to the target size.

## Ids

`<filename>#<n>`, where n counts chunks within that document in order. Re-running
over an unchanged file gives the same ids. **Editing a document can renumber
everything after the edit**, so ids are stable across runs, not across revisions.
Numbering is per document, so editing one file never renumbers another. If
citations must survive revisions, the id would need to hash the content, and that is
a decision for the coordinators; it has not been taken here.

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
- `.docx` is tested on a synthetic file only, not on a real one.
- Sentence splitting (only for units over the ceiling) knows a few abbreviations
  (`Art.`, `sig.`, `n.` ...) and nothing else.
- Hyphen handling is a heuristic: a compound not in the short list is joined.

## Checking the numbers above

CI cannot check "7 documents, about 110 chunks": it only sees the synthetic
fixtures. On a machine with the real `data/`:

```
make ingest        # writes build/chunks.jsonl, warnings name anything skipped
python -c "import json,collections; c=collections.Counter(json.loads(l)['source'] for l in open('build/chunks.jsonl')); print(len(c), sum(c.values())); print(c)"
```

Expect 7 sources and a total near 110. Also read the `skipped as labels` warnings.
Re-check after the documents change; if the counts drift a lot, update this file.
