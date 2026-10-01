# Evaluation

> **TEAM 5 owns this directory.** This file is a template with the sections you
> must fill in. Every heading below is a question you have to answer in writing
> before 17:00.

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

<!-- FILL THIS IN. It is the most important paragraph in the file. -->

The seed set in `questions.yaml` was written from the synthetic fixtures, by
someone who has never lived at Nest. Replace this paragraph with the truth about
your set: how many came from a staff member, how many from residents' own
experience, how many were mined from documents.

## What that biases

<!-- FILL THIS IN. -->

Say it plainly. For example:

> Eleven of our fourteen questions were written by residents. Residents ask
> about rules and opening hours; parents ask about money, safety and contracts.
> Our set therefore over-measures the first and under-measures the second, and
> our correctness number is optimistic for the `public` tier for that reason.

A biased set that names its bias is a scientific instrument. A biased set that
does not is a marketing claim.

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

Results are committed. They contain questions and scores, never Nest documents.
In March 2027 the first thing anyone does is open October's scorecard.

## Red team

`redteam.yaml` holds the attacks and their outcomes. Findings go in
`FINDINGS.md` — what worked, what did not, what is still open. Write it as
though the person reading it has to fix it and was not in the room, because in
March that is exactly who reads it.
