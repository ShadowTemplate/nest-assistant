# TEAM 1 — INGEST
### *documents in, clean text out*

**You own** `src/nest_assistant/ingest/__init__.py`:

```python
build_chunks(src: Path) -> list[Chunk]
```

**You consume** the Nest Drive folder (or `fixtures/` until it arrives).
**You feed** INDEX — and through them, everyone. Nothing downstream can see a
document you did not emit, or fix a tier you got wrong.

| | Task | Block | |
|---|---|---|---|
| A | W1-1.1 Data inventory | 150 min | |
| B | W1-1.2 Ingestion pipeline | 105 min | |
| C | W1-1.3 Chunking comparison | 60 min | **droppable** |

---

## A · Data inventory — the first honest answer to "what does Nest have?"

**Produce** `data/manifest.yaml` — one entry per document: title, filename,
format, language, **tier**, last-updated, owner, and one line on *what kinds of
question this could answer*. Plus `data/INVENTORY.md`, summarising what exists,
what is missing, and what is stale.

**Done when** every file in Drive appears exactly once in the manifest with a
tier assigned, **and `INVENTORY.md` names at least three questions the corpus
cannot currently answer.**

That last part is the point. Knowing the gaps is worth more than cataloguing the
contents, and it tells EVAL what should fail.

> **Stuck 15 min?** Copy `fixtures/manifest.yaml` and start filling it in. If the
> mess feels like you are doing it wrong — you are not. The mess *is* the
> finding, and it goes in `INVENTORY.md`.

## B · Ingestion pipeline — make it real

**Produce** a working `build_chunks()`; a generated `build/chunks.jsonl`
(gitignored); a note on the chunking strategy you chose and why.

**Done when** `make ingest` produces chunks from real Nest documents, every chunk
carries the tier it inherited from the manifest, and INDEX can consume the file
without asking you a question.

Three things the docstring will hold you to:

- **Stable ids.** Re-running over an unchanged document produces the same ids. A
  citation that moves is worthless.
- **No manifest entry → not ingested.** Never default a document to `public`.
  That is how a private document leaks.
- **Clean text.** No page furniture, no repeated headers, no `\x0c`.

> **Stuck 15 min?** `uv run pytest tests/test_components.py -k ingest` says
> exactly what "working" means. Run it first, then make it pass.

## C · Chunking comparison *(droppable — cut this first if the day runs slow)*

Two strategies (fixed-window vs. structure-aware), measured against EVAL's
retrieval set, with a recommendation and numbers. Needs W1-5.1 and W1-2.1.

**Done when** you can say "we chose X, it beat Y by N points on retrieval hit
rate", rather than "we chose X".

---

## Not yours to change

`Chunk` in `schema.py`, and the `chunks.jsonl` format. If either genuinely has
to change, it goes through the coordinators *before* you write the code.

## Ask the coordinators, not Gianvito

**"What tier should this document be?"** Tier is a policy judgment wearing the
costume of a data-entry task, and the coordinators keep the register so that six
teams do not answer it six different ways. Bring them the hard cases — expect
three or four genuinely contested ones, and expect the argument to be the most
useful ten minutes of your morning.
