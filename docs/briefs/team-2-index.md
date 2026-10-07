# TEAM 2 — INDEX
### *text in, relevant text out*

**You own** `src/nest_assistant/index/__init__.py`:

```python
search(q: str, tier: Tier, k: int) -> list[Chunk]
```

**You consume** `build/chunks.jsonl` from INGEST — their stub works until theirs
is real, so you are not waiting for anybody.
**You feed** ANSWER, and every metric EVAL puts on the board.

| | Task | Block | |
|---|---|---|---|
| A | W1-2.1 Embeddings and vector index | 120 min | |
| B | W1-2.2 Tier-filtered retrieval | 60 + 60 min | **the important one** |
| C | W1-2.3 Hybrid search (BM25) | 75 min | **droppable** |

---

## Read this before you write anything

**The stub does not filter by tier.** Ask it a question as `public` and it hands
you a `staff` chunk. That is deliberate, it is today's most dangerous bug, and it
is your task B. `make eval` reports it as **tier leaks, in red**, from 10:00 —
and when you fix it, it goes green in front of the whole room.

There is a second filter downstream in `pipeline.py` so the leak never reaches a
real user. Do not treat it as your safety net. Defence in depth means two
independent layers that both work, not one layer and one excuse.

## A · Embeddings and vector index

**Produce** a working `search()`, a persisted index, and a README section on which
embedding model you chose **and why it matters that it handles Italian**.

**Done when** *"quanto costa una stanza singola?"* returns chunks a human agrees
are relevant — note that the price list says *retta annuale … Singola* and shares
almost no words with the question (*costa* ≠ *retta*, *stanza* ≠ *camera*) — and
you can explain the ranking.

> **Stuck 15 min?** `NEST_EMBEDDING_MODEL` in `config.py` has a starting model,
> downloaded by `make setup` (or `make warm`; `make check` says if it is
> missing). It is a starting point, not a recommendation: measure it against an
> English-first model and write down the difference. That measurement is half
> the task.

## B · Tier-filtered retrieval — your definition of done is a test

**Produce** tier filtering inside `search()`; a passing test suite; and a short
written comparison of **query-time filtering vs. separate per-tier indices**.

**Done when** `tests/test_components.py::test_public_never_sees_private` passes —
**delete the `@pytest.mark.skip` above it** — and you can state in one sentence
why filtering at query time is not sufficient on its own.

The written comparison is the real deliverable. Both designs are defensible and
the trade-off is real (index size and freshness vs. blast radius of a filtering
bug). Arguing it out is worth more than whichever one you pick.

## C · Hybrid search *(droppable)*

Vectors are bad at exact tokens — room numbers, dates, prices, surnames. Add BM25
alongside the vectors with fused ranking, measured against EVAL's set.

**Done when** you can show a query that hybrid gets right and vectors alone get
wrong — or show that there isn't one, which is also a result.
**Good task for a mathematician or a physicist.**

---

## Not yours to change

`Chunk`, and the shape of what you return: ranked best-first, at most `k`,
deterministic for the same query and corpus. EVAL cannot compare October with
March if your ordering wobbles.

## Ask the coordinators, not Gianvito

**"Has INGEST's real output landed, and did the chunk ids change?"** They track
which stubs have flipped. Ask them rather than reading team 1's git history —
and tell them the moment your filter is live, because that is a board update the
whole room wants to see.
