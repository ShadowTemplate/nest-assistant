# Evaluation

> **TEAM 5 owns this directory.** This file is a template with the sections you
> must fill in. Every heading below is a question you have to answer in writing
> before 17:30.

## What is measured

| Metric | Meaning | Target |
|---|---|---|
| `retrieval_hit_rate` | Fraction of questions where at least one expected source was retrieved | higher |
| `answer_correctness` | Fraction of answerable questions answered correctly | higher |
| `refusal_precision` | Of the refusals, how many were right to refuse | higher |
| `refusal_recall` | Of the questions that should be refused, how many were | higher |
| `tier_leaks` | Chunks returned above the asker's tier | **zero. Not "low".** |

Precision and recall are both there on purpose. A system that answers everything
scores perfectly on recall of answerable questions and appallingly on refusals; a
system that refuses everything does the reverse. Neither is good, and a single
number would hide it.

## Where the questions came from

`questions.yaml` holds 94 questions. 62 are tagged `source: document`: they
were written from Nest's documents (the PDFs in `data/` and the synthetic
fixtures). 32 are tagged `source: resident` (q063–q094): written by residents
about daily life in the house, all `tier: resident` and all valid only on
`fixtures/`. None are tagged `staff`, and none come from a poll of real parents.

> TEAM 5: if some of these were really written from your own experience as
> residents, or from other teams, change their `source` tag and update this
> paragraph. The tags must match the truth.

Breakdown by tier and expected outcome:

| Tier | Should answer | Should refuse |
|---|---|---|
| public | 41 | 7 |
| resident | 38 | 6 |
| staff | 2 | 0 |

By corpus: 50 questions valid on both, 8 only on `data/`, 36 only on
`fixtures/`. A run on `data/` uses 58 questions, a run on `fixtures/` 86.

## What that biases

- **Document-derived questions are answerable by construction.** A question
  written by reading a paragraph is one the corpus can answer. Real users ask
  things no document covers, and the set under-represents them. Only 13 of 94
  questions expect a refusal, so `refusal_recall` rests on a small sample.
- **The resident voice only reaches `fixtures/`.** All 32 resident-written
  questions are tagged `corpus: fixtures`, so a scorecard on the real `data/`
  corpus is still entirely document-derived.
- **`staff` is nearly absent (2 of 94).** Public has 48 and resident 44. A
  `staff` result is anecdotal, and tier-boundary behaviour is measured on few
  cases.
- **No parent voice.** Nobody outside the documents contributed. Parents ask
  about money, safety and contracts in loose wording, with typos and often in
  other languages; this set mostly reflects how the documents phrase things.
  Our `public` correctness number is therefore optimistic.
- **Facts are easy to match.** Most expected answers are one number or date, so
  a correct answer is easy to recognise and the number flatters the system on
  questions needing explanation or several documents.

A biased set that names its bias is a scientific instrument. A biased set that
does not is a marketing claim.

## How correctness is judged

`answer_correctness` is decided by an LLM judge (`JUDGE_MODEL`, set separately
from `ANSWER_MODEL` in `config.py`). It is given the question, the key fact in
`expected_answer` and the answer, and says whether the answer states that fact,
however it is worded. The old substring check failed correct answers worded
differently.

**What it costs.** The judge is `JUDGE_MODEL`, by default `claude-opus-5-5`,
the strongest and most expensive model in the stack, on purpose (see
`config.py`). It makes one call per answerable question that was not refused:
at most 49 calls for a run on `data/` and 74 on `fixtures/`, every time you run
`make eval` or `make eval-save`. Each call is small (question, expected fact and
answer in; at most 5 tokens out), but they add up over a day of iterating. To
save money while iterating, set `NEST_JUDGE_MODEL` in `.env` to a cheaper model;
for any scorecard you commit, use the default, because scorecards are only
comparable if the same judge graded them. With no API key, no judge call is
made.

- If no model is reachable, the harness falls back to substring matching and
  says so in the scorecard `notes` (`N substring fallback`). A scorecard with
  fallbacks is not comparable with one without.
- Each row in `details` records `correct` and `judged_by` (`llm` or
  `substring`), so verdicts can be read one by one.
- **Not yet validated.** The judge has not been spot-checked against human
  verdicts. Until someone reads a sample of verdicts and records here how often
  the judge was wrong, treat `answer_correctness` as indicative only.
  Spot-check result: _not done yet_.

### Metrics cannot be gamed in either direction

`tests/test_evaluate.py` checks the scorer with fake pipelines: one that
answers everything gets `refusal_recall` 0; one that refuses everything gets
`answer_correctness` 0 and low `refusal_precision`. A leaked chunk is counted
in `tier_leaks`, measured on raw retrieval before any filtering.

## What the corpus cannot answer

<!-- FILL THIS IN, together with TEAM 1's data/INVENTORY.md -->

List the questions that no document can answer. These are the questions that
*must* be refused — and they are also the shopping list for whoever asks Nest for
more documents before March.

## Running it

```bash
make eval              # print the scorecard
make eval-save         # print it and write a dated file to eval/results/
```

Results in `eval/results/` are committed. They contain questions and scores, and
answer text **only for `public` questions**: an answer to a resident or staff
question quotes resident or staff documents (the residents' guide holds the wifi
password), so its text is written as `(withheld: resident tier)`. Everything
else about it — score, refusal, cited chunk ids, leaks — is kept.

`--save` also writes a full copy, every answer included, to
`build/eval-results/`. That folder is gitignored: use it to debug, never commit
it. In March 2027 the first thing anyone does is open October's scorecard.

## Red team

`redteam.yaml` holds the attacks and their outcomes. Findings go in
`FINDINGS.md` — what worked, what did not, what is still open. Write it as
though the person reading it has to fix it and was not in the room, because in
March that is exactly who reads it.
