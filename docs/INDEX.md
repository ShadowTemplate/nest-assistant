# How INDEX finds the right text, and keeps the wrong text out

> **TEAM 2 owns this document.** It holds the two written deliverables of the
> day: which embedding model we chose and why (W1-2.1), and how tier filtering
> is designed (W1-2.2).

## What `search()` does

```
question + tier
   │
   ├─ 1. drop every chunk this tier may not see        (never scored, never returned)
   ├─ 2. turn the question into a vector               ("query: " + question)
   ├─ 3. score the remaining chunks: cosine similarity  (one dot product each)
   └─ 4. return the best k, highest first               (ties keep document order)
```

Chunk vectors are computed once and saved in `build/index/` (`embeddings.npy`,
plus `meta.json`, which you can read in a text editor). `meta.json` holds a
SHA-256 fingerprint of the model name and every chunk's id and text. If any of
those change, the index is rebuilt on the next search; otherwise it is loaded
from disk in under a millisecond. The saved index holds only vectors and ids,
never text or tiers: tiers always come from the live corpus, so a stale index
cannot hand anyone an out-of-date permission.

Speed on a laptop: about 12 ms per question. The first question after a process
starts takes about 5 s, which is loading the model. The bot should call
`index.build_index()` at startup so no resident pays that cost.

## W1-2.1 · Which embedding model, and why Italian matters

**Chosen: `intfloat/multilingual-e5-small`** (`NEST_EMBEDDING_MODEL` in `config.py`).

An embedding model places each text on a "map of meaning": texts that mean the
same thing land close together, even when they share no words (*quanto costa una
stanza* vs *retta annuale camera singola*). How well it does that depends on what
it was trained on. Our questions and almost all our documents are Italian. A model
that learnt mostly from English does not really read them, so it places them
badly on the map and the right paragraph sinks down the ranking.

We measured three models through the same `search()`, same chunks, same tier
filter. A question's *right piece* is a chunk from an expected source that
contains the expected fact from `eval/questions.yaml`.

| Model | Trained on | Fixtures: right piece 1st | Real docs: right piece 1st | Real docs: right piece in top 3 |
|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` (starting point) | sentence ↔ similar sentence, many languages | 53% | 53% | 59% |
| `all-MiniLM-L6-v2` | English first | 40% | 29% | 53% |
| **`multilingual-e5-small`** | **short question → passage that answers it**, many languages | **93%** | **65%** | **76%** |

`make eval` retrieval hit rate on the real documents: 89% with the starting
model, **94%** with e5-small. Tier leaks are 0 with both.

What the numbers mean:

- **The English-first model fails on Italian, as expected.** On three Italian
  questions (meals included in the fee, quiet hours, a training weekend) it put
  the right piece 26th, 40th and 46th out of 121, where e5-small put it 1st, 4th
  and 1st.
- **Question → passage training is what helps.** Users type short questions;
  documents are long paragraphs and tables. e5 was trained on exactly that pair.
  It also fixed tables of prices, which the starting model ranked below prose
  that merely talked about money.
- **No model solves cross-language questions.** An Italian question whose answer
  exists only in an English document was ranked 11th, 56th and 44th by the three
  models. Keyword search (W1-2.3) or duplicating the fact in the Italian
  documents are the real fixes.

Caveats, written down so nobody over-reads the table:

- 15 (fixtures) and 17 (real) answerable questions: one question moves a
  percentage by 6–7 points.
- The real documents were cut into pieces page by page by a scratch script, not
  by INGEST. Re-run the comparison when INGEST lands: chunking changes the result.
- e5 needs `"query: "` before questions and `"passage: "` before chunks;
  `index._prefixes()` adds them. Changing model without that would quietly cost
  accuracy.

**To re-measure:** set `NEST_EMBEDDING_MODEL` to another model in `.env`, run
`make warm` and then `make eval`. The index rebuilds itself because the model
name is part of the fingerprint. `tools/index_map.py` draws the result.

### What the scores mean (for ANSWER)

Scores are cosine similarities. With e5-small they are compressed: almost
everything lands between 0.78 and 0.90. **The ranking is meaningful; the absolute
value is not a refusal signal.** On the real documents, questions that should be
refused scored 0.80–0.83, inside the range of correct answers (0.78–0.89).
Deciding to refuse has to come from reading the chunks, not from a threshold on
our score.

## W1-2.2 · Tier filtering: query-time filter vs. one index per tier

**One sentence:** filtering at query time is only as good as the tier label on
each chunk and the one line of code that applies it, so it needs a second,
independent layer, because a single bug or a single mislabelled document leaks
everything that mistake touches.

### The two designs

| | **A. One index, filter at query time** (what we built) | **B. One index per tier** |
|---|---|---|
| How | All chunks in one index; each search drops chunks above the caller's tier before scoring | Three indices: public, public+resident, everything. The caller's tier picks which index to open |
| Where a bug leaks | A bug in the filter can expose every tier at once | A caller can only reach the index they are given; a bug in ranking cannot cross indices |
| Size and build time | One copy of every vector | Public chunks are stored three times, resident chunks twice |
| Freshness | One rebuild when documents change | Three rebuilds, which must stay in sync. A document whose tier changes must leave one index and enter another |
| A mislabelled chunk | Shown to whoever its wrong label allows | Shown to whoever its wrong label allows. **Same failure: neither design fixes a wrong label** |
| Code | One function, easy to test exhaustively | More moving parts: index selection, three build paths |

**Why we chose A.** The corpus is small (hundreds of chunks), so B's size cost is
not the issue; freshness and simplicity are. One index means one rebuild and one
place to test. B's real advantage, that a filtering bug cannot leak across tiers,
we get differently: by filtering **before** scoring rather than after.

**When to switch to B.** If the corpus grows to the point where staff documents
are numerous and sensitive (contracts, personal data), the blast radius argument
wins: a separate staff index can live in a separate place with separate access,
which a filter in one shared file never can.

### How A is defended

1. **Filter before ranking.** Forbidden chunks are removed first and never
   scored. No ranking bug can promote something that was never in the list.
2. **Fail closed on bad labels.** A chunk whose tier is not one of
   `public | resident | staff` (a typo like `"Staff "`) is hidden from everyone,
   not shown. An unknown *caller* tier raises an error, which the pipeline turns
   into a refusal.
3. **Check the output.** Before returning, `search()` re-checks every result and
   raises if anything is above the caller's tier.
4. **A second, independent layer.** `pipeline.ask()` filters again with its own
   code. EVAL measures leaks on our raw output, before that layer, so the board
   shows our bugs rather than hiding them.
5. **Tests.** `test_public_never_sees_private` runs every question in
   `eval/questions.yaml` against all three tiers with `k=100`;
   `test_chunk_with_broken_tier_is_hidden` and `test_unknown_caller_tier_is_refused`
   cover the failure cases.

What none of this protects against: **a document given the wrong tier in the
manifest.** That is a policy decision made by a person (INGEST, W1-1.1), and the
best defence is a second person checking it.

Results: tier leaks went from **37** (the stub) to **0**, and stay at 0 on the
fixtures, the real documents and every question × tier combination.
