# How INDEX finds the right text, and keeps the wrong text out

> **TEAM 2 owns this document.** It holds the written deliverables of the day:
> which embedding model we chose and why (W1-2.1), how tier filtering is
> designed (W1-2.2), and what keyword search adds (W1-2.3).

## What `search()` does

```
question + tier
   │
   ├─ 1. drop every chunk this tier may not see        (never scored, never returned)
   ├─ 2. meaning: cosine similarity to the question    ("query: " + question)
   ├─ 3. keywords: BM25 re-orders meaning's top 5       (exact words and numbers rise)
   └─ 4. return the best k, highest first               (ties keep document order)
```

Chunk vectors are computed once and saved in `build/index/` (`embeddings.npy`,
plus `meta.json`, which you can read in a text editor). `meta.json` holds a
SHA-256 fingerprint of the model name and every chunk's id and text. If any of
those change, the index is rebuilt on the next search; otherwise it is loaded
from disk in under a millisecond. The saved index holds only vectors and ids,
never text or tiers: tiers always come from the live corpus, so a stale index
cannot hand anyone an out-of-date permission.

Speed on a laptop CPU: about 30 ms per question. **The first question after a
process starts takes ~5 s** (loading the model). `index.warm()` does that work up
front; **the bot should call it at startup** so no resident waits. It downloads
nothing.

## W1-2.1 · Which embedding model, and why Italian matters

**Chosen: `intfloat/multilingual-e5-base`** (`NEST_EMBEDDING_MODEL` in `config.py`).
It started as e5-small; the upgrade to e5-base, measured on Team 1's chunks, is
at the end of this section.

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

### Upgrade: e5-small → e5-base, on Team 1's chunks

Once Team 1's chunks existed, the weak spot was first place (50%). We tried a
free idea first, then a bigger model. Both inside INDEX; no other team's code.

| Hybrid search, right chunk 1st / top 3 / top 5 / MRR | e5-small | **e5-base** |
|---|---|---|
| Team 1 chunks (what the assistant searches) | 50% / 72% / 89% / 0.63 | **61% / 89% / 94% / 0.74** |
| Fixtures | 93% / 100% / 100% / 0.97 | 93% / 100% / 100% / 0.96 |
| Scratch chunks of the real PDFs | 71% / 82% / 88% / 0.77 | 65% / 82% / **94%** / 0.75 |
| Time per question (laptop CPU) | 12 ms | 30 ms |

`make eval` retrieval hit rate on Team 1's chunks: 89% → **94%**. Tier leaks 0.

- **Rejected first: the section heading in front of each chunk** ("passage: {section}
  {text}"). Same or worse on all three corpora (fixtures 93% → 87% first place).
- **e5-base did not pass the rule we set in advance** (better first place, no lower
  top 5, on every corpus): it loses one question on the scratch chunks. We chose
  it anyway because Team 1's chunks are what the assistant actually searches, and
  there it gains two questions in first place and the top 5 goes from 89% to 94%.
  That is a judgement, written down so March can revisit it with more questions.
- On Team 1's chunks e5-base is better on six questions (e.g. *"Chi abita nella
  camera 120?"* 8th → 1st, *"Come segnalo un guasto?"* 4th → 1st) and worse on
  three; the hybrid's keywords bring two of those (single and triple room
  prices) back from 5th to 3rd.
- Larger models (e5-large, bge-m3, 2.2 GB+) were not tested: CPU only, and the
  1-second budget. A cross-encoder re-ranker was tested and not shipped (below).

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

## W1-2.3 · Hybrid search: what keywords add

**Final design: meaning picks the five candidates, keywords re-order them.** The
five chunks ANSWER reads are always exactly the five meaning search would pick;
keywords only change their order. They can promote an exact match ("camera
tripla", "cena comunitaria", a price) and can never push a good chunk out.

### How we got there

Every step measured with `tools/retrieval_report.py`. **Rule: choices were made
on the fixtures only; the real documents were the exam, never used to choose.**
"Right chunk" = a chunk from an expected document containing the expected fact.
MRR scores 1 for first place, ½ for second, ⅓ for third..., averaged.

| Step | What changed | Fixtures: 1st / top 5 / MRR | **Real docs: 1st / top 5 / MRR** |
|---|---|---|---|
| C0 | meaning only (e5-small), the baseline | 93% / 100% / 0.97 | 65% / 88% / 0.73 |
| C1 | keyword only, BM25 on plain words | 67% / 87% / 0.77 | 47% / 82% / 0.61 |
| C2 | keyword only, Italian-aware words | 80% / 93% / 0.86 | 59% / 76% / 0.67 |
| C3 | fuse everything, equal weights | 87% / 93% / 0.91 | 65% / 82% / 0.72 |
| C4 | leave chunks with no shared word out of the fusion | 87% / 93% / 0.91 | 65% / 82% / 0.72 |
| C5 | keyword weight 0–1.5 tried; 0.5 best on fixtures | 93% / 93% / 0.94 | 65% / 82% / 0.72 |
| C6 | meaning picks 5, keywords re-order them | 93% / 100% / 0.96 | 71% / 88% / 0.77 |
| C7 | fusion `k` 60 → 2 inside the re-ordering | 93% / 100% / 0.97 | 71% / 88% / 0.77 |
| **C8** | **embedding model e5-small → e5-base** | **93% / 100% / 0.96** | **65% / 94% / 0.75** |

C6/C7 against meaning alone, on the real documents: right chunk first 65% → **71%**,
in top 3 76% → **82%**, right document first 76% → **82%**, MRR 0.73 → **0.77**,
in top 5 unchanged at 88% (by construction). `make eval` retrieval hit rate is
94% either way, and tier leaks stay 0.

**Italian-aware words** (C2): accents dropped (*puo* matches *può*), Italian and
English stopwords removed, the final vowel of longer words cut so *singola /
singole / singoli* match, and numbers kept whole (*10.450*, *23:00*, *31/07*).
It lifted keyword-only first place from 47% to 59% on the real documents.

**Why plain fusion was rejected** (C3–C5). It improved "right document first" but
pushed one right chunk per corpus out of the top 5: when the question and the
document use different words (*dormire un amico* vs *ospiti*), keywords vote
for the wrong chunks and out-vote meaning. Re-ordering only meaning's top five
keeps the gain and removes that failure.

**Why C7.** Rank fusion gives a chunk `1 / (k + position)`. The paper's `k = 60`
is meant for long lists; inside five candidates it makes 1st and 5th almost
equal (1/61 vs 1/65), so keywords could barely re-order anything. Team 1's
chunks exposed it (below). `k` and the keyword weight were swept on the two dev
sets (fixtures and the scratch chunks); the rule, fixed before looking at the
result, was "highest mean MRR on the dev sets". It picked `k = 2`, weight 0.5.

### On Team 1's chunks (the exam)

Team 1's `build/chunks.jsonl`: 111 chunks from all 7 documents, ids unique,
every tier matching the manifest, the staff room list included. These numbers
were not used for any choice above.

| 18 questions | right 1st | top 3 | top 5 | MRR | right doc 1st | tier leaks |
|---|---|---|---|---|---|---|
| meaning only | 50% | 61% | 89% | 0.62 | 67% | 0 |
| keyword only | **56%** | **72%** | 83% | **0.66** | **72%** | 0 |
| hybrid (C7, e5-small) | 50% | **72%** | **89%** | 0.63 | 67% | 0 |
| **hybrid with e5-base (C8, what `search()` uses)** | **61%** | **89%** | **94%** | **0.74** | **89%** | 0 |

`make eval` (no API key, retrieval only): hit rate 89% (94% with e5-base), tier leaks 0, now with a
staff document in the corpus.

What changed with Team 1's chunking:

- **Better:** headings stay with their content, so *"A che ora inizia il
  silenzio?"* went from 4th (scratch chunks) to **1st**.
- **Worse for meaning:** the three price questions (single, double, triple room)
  dropped to 5th, where keywords put two of them 1st. The hybrid only lifts
  them to 4th: it is built never to let keywords override meaning by much.
- **Keyword search beats meaning on these chunks**, the opposite of the dev sets.
  Settings that favour keywords more (weight 2) would score 61% here but lose
  on both dev sets; picking them now would be tuning on the exam. With 15–18
  questions per set, these differences are one or two questions.

**Next:** Team 1's chunks are now the real corpus, so they should become the
dev set, and the comparison needs a fresh, larger question set to test on
(TEAM 5, W1-5.1). Until then, keep the fusion settings chosen by the rule.

### Done-when: a query hybrid gets right and vectors get wrong

- **"Quanto costa una camera singola?"** (real documents): meaning put the price
  table 2nd; hybrid puts it **1st**, because *camera* and *singola* appear
  verbatim in the table.
- **"Quando si fa la cena comunitaria?"** (fixtures): 2nd → **1st**, for the same
  reason: an exact phrase meaning search blurred.

The price for that: **"A che ora inizia il silenzio la sera?"** slips from 4th to
5th on the real documents (still read by ANSWER), and **"Posso far dormire un
amico?"** from 1st to 3rd on the fixtures.

### What keywords cannot fix

- **Cross-language questions.** An Italian question whose answer exists only in
  an English document shares no words with it: keywords do not help (44th either
  way). Only a better cross-lingual model or the fact in the Italian documents fixes it.
- **A heading split from its content.** On the real documents the word
  *silenzio* and the time *23:00* ended up in two different chunks (the scratch
  chunker cut mid-page). Keywords find the heading, not the answer. **For INGEST:
  never separate a heading from what follows it.**

### A side benefit: the no-model fallback

Keyword search needs nothing installed, so it is now what `search()` uses when
the embedding model is missing (`make setup-lite`, CI). Before, that fallback
returned chunks in document order: right chunk first went from **0%** to **59%**
on the real documents and from 0% to 80% on the fixtures.

### Reproduce it

```bash
uv run python tools/retrieval_report.py --label "what I changed" --methods vector,keyword,hybrid
uv run python tools/retrieval_report.py --html     # draws every saved run
```

Both write under `build/` (gitignored): the report quotes chunk ids and, on
`data/`, describes Nest's documents.

## Tried, not shipped: a cross-encoder re-ranker

After e5-base, Team 1's chunks still had the right chunk first only 61% of the
time. We looked at every miss before trying anything else:

| Cause | Questions | Fix |
|---|---|---|
| Two chunks look alike to a one-vector model: *fees* (`6. RETTA`) and *merit support* (`7. SOSTEGNO AL MERITO`) both list room types and euro amounts | single / double / triple room price | open: a re-ranker was tried (below) |
| The fact exists only in the English brochure | deposit | data: put it in the Italian documents |
| The automatic "right chunk" label is blunt (contains a word ≠ answers the question) | breakdown report, online interview | TEAM 5: a hand-checked question set |
| A superseded document competes with the current one | training weekend, prices | TEAM 1: drop the *Proposta* brochure from the manifest |

**What-if for TEAM 1, measured on the shipped search (e5-base hybrid):** with the
superseded *Proposta* brochure left out of the corpus, right chunk first goes
61% → 67% and right document first 89% → 94%. Removing it is TEAM 1's call.

**What we tried.** A multilingual cross-encoder
(`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, 470 MB) that reads the question and
a chunk *together*, used to re-order the top five. On the 18 questions every
choice had been made on, it looked good:

| Original questions: right chunk 1st / top 3 / MRR | e5-base hybrid | + re-ranker |
|---|---|---|
| Team 1 chunks | 61% / 89% / 0.74 | 72% / 94% / 0.83 |
| Scratch chunks | 65% / 82% / 0.75 | 76% / 94% / 0.85 |
| Fixtures | 93% / 100% / 0.96 | 100% / 100% / 1.00 |

**Why it is not shipped: the fresh-question check.** When TEAM 5 added 32 public
questions (PR #7), we re-measured on those alone: questions that played no part
in any choice.

| Never-seen questions: right chunk 1st / top 5 / MRR | e5-small hybrid | **e5-base hybrid (shipped)** | e5-base + re-ranker |
|---|---|---|---|
| Real documents, Team 1 chunks (23 q)* | 43% / 70% / 0.56 | **57% / 78% / 0.66** | 35% / 78% / 0.57 |
| Fixtures (31 q) | **90% / 97% / 0.93** | 87% / 94% / 0.91 | 77% / 94% / 0.84 |

\* The new questions list only fixture files as sources, so for this check a
real chunk counted as right if it contains the expected fact (questions whose
fact appears in more than five chunks left out). Looser than a hand-checked set.

- **e5-base holds up:** clearly better on the real documents (+14 points first
  place, +8 top 5), one question worse out of 31 on the fixtures.
- **The re-ranker does not:** on never-seen questions it is *worse* in first place
  on both corpora. The failures are real, not label noise: *"C'è l'aria
  condizionata?"* and *"C'è un parcheggio?"* put the deposit paragraph and the
  admissions heading first, pushing the list of included services to 5th. Its
  gains on the original 18 questions were partly a fit to those questions.
- It would also have cost 470 MB per laptop and made the first question ~18 s.

**A correction.** The first version of PR #14 described the re-ranker as shipped,
but `search()` still called the hybrid ranking: only `search_with_scores`'s
default had changed, and the pipeline calls `search()`. The review caught it.
The re-ranker has been removed, and `test_search_uses_the_hybrid_ranking` now
checks which ranking `search()` actually calls, not just its output.

**For later.** The look-alike problem is real. Worth re-testing with a stronger
re-ranker once there is a GPU and TEAM 5's hand-checked question set, judged on
never-seen questions from the start.

**For TEAM 5:** add the real PDF names to `expected_sources` for q031–q062 (or tag
them `corpus: fixtures`). As they stand, `make eval` on `data/` counts them as
retrieval misses whatever the search does.

## Short questions and messages that ask two things

Two complaints from using the bot: very short questions find nothing, and a
message that asks two things gets half an answer. Every measurement here goes
through `index.search()`, the function the pipeline calls.

### Keyword rescue (shipped)

*"singola?"* says almost nothing to a vector: on Team 1's chunks meaning ranked
the price chunk 14th, while BM25 ranked it 1st. Keywords only re-order meaning's
top five, so they could not bring it back. Now **keywords' best match takes the
fifth place if meaning missed it**; places 1–4 never move.

To test it fairly, each labelled question was reduced to its single most
distinctive word (*"Quanto costa una camera singola?"* → *"singola?"*):

| Right chunk in the top 5 | before | **with rescue** |
|---|---|---|
| One-word questions, Team 1 chunks (41) | 24% | **32%** |
| One-word questions, fixtures (46) | 50% | **52%** |
| Every normal question set (first place, top 3, top 5) | — | unchanged |

*"singola?"* now brings the price chunk into the top 5 (5th, from 14th). The one
cost: on two-question messages in the fixtures, one pair in 22 lost its second
answer to the rescued chunk.

### Splitting a message into its questions (tried, not shipped)

We split messages at `?`, `;` and "e quando / e come…", searched each part, and
took the results in turns. Tested on two-question messages built from pairs of
labelled questions (*"X? Y?"*, *"X e Y?"*):

| Both answers in the 5 chunks ANSWER reads | no splitting | splitting |
|---|---|---|
| Team 1 chunks (20 pairs) | **60%** | 55% |
| Fixtures (22 pairs) | 91% | **100%** |

Worse on the real documents, so not shipped. Five places shared by two or
three searches leave each part about two, and an answer that is third in its own
search is lost. Giving ANSWER more chunks does not change the picture either:
without splitting, both answers are there 60% of the time at k=5, 8 and 10 alike.
**The pairs that fail contain one question that is hard on its own**, so the fix
is better retrieval for single questions, not splitting.

**For TEAM 3:** the search delivers both answers 60% of the time and at least one
90% of the time. If the bot gives no answer at all to a two-part message, check
whether ANSWER refuses the whole reply when only one part is in the chunks.
