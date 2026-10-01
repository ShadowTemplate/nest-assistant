# Architecture

> The one document everybody reads. It has to make sense to a second-year
> physics student who has never built anything with an AI. If any part of it
> does not, that is a bug — tell us and we will fix the document.

## What we are building

An assistant that answers questions about the Nest residence — from students,
from their parents, and from the staff — over Telegram, in Italian.

It answers **only from Nest's own documents**. It is not a chatbot that knows
things; it is a system that finds the right paragraph and then explains it. When
the documents do not contain the answer, the correct behaviour is to say so.

## The idea in one picture

```
   "Quanto costa una singola?"
   from telegram user 12345
            │
            ▼
   ┌─────────────────┐
   │   identity      │   who is asking?   → public | resident | staff
   └────────┬────────┘
            │  tier
            ▼
   ┌─────────────────┐    ┌──────────────────────────────────┐
   │     index       │◄───┤  chunks.jsonl                    │
   │   search()      │    │  ▲                               │
   └────────┬────────┘    │  │ built by ingest.build_chunks()│
            │             │  │                               │
            │             │  └── data/  (real Nest documents) │
            │             │      fixtures/ (synthetic)        │
            │             └──────────────────────────────────┘
            │  3–5 relevant chunks THIS PERSON MAY SEE
            ▼
   ┌─────────────────┐
   │     answer      │   write an Italian answer using ONLY those chunks,
   │   generate()    │   and cite them — or refuse
   └────────┬────────┘
            │  Answer(text, citations, confidence, refused)
            ▼
   ┌─────────────────┐
   │   guardrails    │   last check before a human reads it
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐          ┌──────────────────────────┐
   │      bot        │          │        evaluate          │
   │   Telegram      │          │  is any of this any good? │
   └─────────────────┘          └──────────────────────────┘
```

This shape has a name: **RAG**, retrieval-augmented generation. Retrieve first,
generate second. The model is the last step, not the first, and it is the step
we trust least.

## The three types everything is built from

In `src/nest_assistant/schema.py`. Read that file — it is short, and it is the
only thing all six teams share.

```python
Tier = "public" | "resident" | "staff"     # ordered, ascending privilege

Chunk:   id, text, source, tier, lang, section
Answer:  text, citations, confidence, refused
```

**`Chunk`** is a piece of a document — a few paragraphs, small enough to retrieve
precisely and large enough to make sense on its own. Its `id` is stable, which is
what makes a citation mean something.

**`Answer`** is what the user reads. `refused=True` is a success, not a failure:
it is the system saying *I don't know, ask the secretariat* instead of inventing
something.

## Tiers: the interesting part

The same question has different correct answers depending on who asks it.

> *"Cosa succede se non pago l'affitto per due mesi?"*

- asked by a **parent** → the assistant should not answer. The real procedure is
  in an internal document.
- asked by the **staff** → the assistant should quote that procedure exactly.

So access control is not a checkbox bolted on at the end. It runs through the
whole system: every chunk carries the minimum tier allowed to see it, and the
retriever filters before anything reaches the model.

**Why filter at retrieval and not in the prompt.** You could tell the model "do
not reveal staff information". You would be relying on a system that can be
talked out of things. If the chunk never arrives, there is nothing to talk it out
of. *The data never arrives* beats *the prompt says not to*, every time.

We do both anyway, in two independent layers:

1. `index.search()` filters by tier (team 2's job).
2. `pipeline.ask()` filters again before the model sees anything.

That is **defence in depth**: two layers that both work, not one layer and one
excuse.

## The six components, and who owns them

| Component | Team | Interface | Job |
|---|---|---|---|
| `ingest` | 1 | `build_chunks(src) -> list[Chunk]` | documents in, clean chunks out |
| `index` | 2 | `search(q, tier, k) -> list[Chunk]` | find the relevant text, for this person |
| `answer` | 3 | `generate(q, chunks, lang) -> Answer` | write the answer, or refuse |
| `identity` | 4 | `resolve(user_id) -> Tier` | who is asking |
| `bot` | 4 | `run()` | the part everyone can see |
| `evaluate` | 5 | `run(pipeline) -> Scorecard` | is any of this working |
| *(the seams)* | 6 | hooks, CI, the checkpoint | make it survive until March |

## Why everything already works on day one

**Every one of those functions is already implemented — badly.** `make demo`
answers a question right now, on a fresh clone, with no API key, no internet and
no data. It answers with three hand-written chunks, an unranked search and a fake
model, and the answer is useless.

That is deliberate, and it is the single decision that makes six teams work in
parallel with one instructor:

- **Nobody is blocked.** Team 3 needs retrieval; the stub retrieval already
  works. Team 5 needs a pipeline to measure; the stub pipeline already runs.
- **Integration is continuous, not an event.** The pipeline is never broken, so
  "does it still work?" is answerable at any minute of the day, by anyone,
  with `make check`.
- **Progress is visible.** `make board` shows which components are STUB and which
  are REAL. Flipping one is a public event.

Your job is to replace *your* stub with something real, behind an interface that
does not change. Every stub is marked:

```python
# ---------------------------------------------------------------------------
# TEAM 2 — REPLACE ME
# ---------------------------------------------------------------------------
```

## Why evaluation exists from hour one

Without it, "is it good?" is a conversation about vibes. With it, the answer is:

> *62% of real questions answered correctly, 91% of unanswerable ones correctly
> refused, zero private chunks leaked.*

`make eval` produces that card. In March 2027 the job is to beat October's
number, and in October 2027 the same card is what tells us whether swapping the
hosted model for a self-hosted one on Nest's own GPUs made things better or
worse. Without it, that swap is an argument. With it, it is a measurement.

## What is not here yet

Written down so nobody thinks it was forgotten:

- Real identity verification. Today it is an allowlist; the design note for the
  real thing is `docs/IDENTITY.md` (team 4), and March implements it.
- Deployment. W1 runs on your laptop, on purpose. The Nest server is a W2 task.
- Conversation memory. *"E la doppia?"* is meaningless to a retriever without the
  question before it.
- English. The `lang` field exists everywhere from day one so that turning it on
  later is a feature, not a rewrite.
- Logging, feedback, GDPR paperwork. All W2.

## Where to look next

- `docs/briefs/` — your team's one-page brief: three tasks, one interface, and
  what "done" means for each.
- `src/nest_assistant/schema.py` — the contracts. Ten minutes, well spent.
- `src/nest_assistant/pipeline.py` — the whole assistant, in thirty lines.
- Your own component's `__init__.py` — your task list is in the module docstring.
- `docs/DATA_POLICY.md` — the one rule with no exceptions.
