"""TEAM 2 — INDEX · *text in, relevant text out*

You own one function::

    search(q: str, tier: Tier, k: int) -> list[Chunk]

Your tasks
----------
W1-2.1  Embeddings and vector index  -> real search, and a written note on which
                                        embedding model you chose and why it
                                        matters that it handles Italian
W1-2.2  Tier-filtered retrieval      -> the most important task on this team
W1-2.3  Hybrid search (BM25)         -> droppable

A warning you should read before you write anything
---------------------------------------------------
The stub below **does not filter by tier**. Ask it a question as ``public`` and
it will hand you a ``staff`` chunk. That is deliberate, it is today's most
dangerous bug, and it is task W1-2.2. ``make eval`` will report it as a tier leak
on the board until you fix it.

There is a second filter downstream in ``pipeline.py`` that stops the leak
reaching a real user. Do not treat that as your safety net: defence in depth
means two independent layers that both work, not one layer and one excuse.

Stuck for 15 minutes?
---------------------
``tests/test_index.py`` has a skipped test named ``test_public_never_sees_private``.
Unskip it. It is your definition of done.
"""

from __future__ import annotations

from ..config import CHUNKS_PATH, DEFAULT_K
from ..ingest import build_chunks
from ..schema import Chunk, Tier
from ..storage import read_chunks

OWNER = "TEAM 2 — INDEX"
INTERFACE = "index.search(q: str, tier: Tier, k: int) -> list[Chunk]"
STATUS = "stub"  # flip to "real" when you replace the body below. `make board` reads this.


def load_corpus() -> list[Chunk]:
    """Chunks from ``build/chunks.jsonl`` if ingestion has been run, else INGEST's stub.

    This is what lets the pipeline answer a question on a freshly cloned repo
    with no data, no API key and no internet.
    """
    chunks = read_chunks(CHUNKS_PATH)
    return chunks if chunks else build_chunks()


# ---------------------------------------------------------------------------
# TEAM 2 — REPLACE ME
# ---------------------------------------------------------------------------
def search(q: str, tier: Tier = "public", k: int = DEFAULT_K) -> list[Chunk]:
    """Return the ``k`` chunks most likely to answer ``q``, for a caller at ``tier``.

    Contract you must satisfy:

    * **Never return a chunk whose ``tier`` outranks ``tier``.** Not ranked last,
      not returned with a warning — never returned. Use
      :func:`~nest_assistant.schema.tier_allows`.
    * Ranked best-first. Everything downstream assumes ``results[0]`` is your
      strongest candidate.
    * At most ``k`` results, possibly fewer. Returning fewer is allowed and
      sometimes correct.
    * Fast enough to sit inside a chat round-trip. Under a second on a laptop.
    * Deterministic for the same query and corpus, so that EVAL can compare
      today's number with March's.

    Things you will discover, all of which are on the syllabus:

    * The search **always** returns something. Ask about keeping a cat when Nest
      has no pet policy and you will get the three least-unrelated chunks in the
      corpus. Similarity is not relevance. ANSWER has to cope with that, so tell
      them what your scores mean.
    * Embeddings are bad at exact tokens — room numbers, dates, prices. That is
      what W1-2.3 (BM25) is for.
    * An embedding model trained mostly on English is measurably worse at
      Italian. Measure it. Do not take anyone's word for it, including this
      docstring's.

    The stub returns the corpus unranked, ignoring the query and the tier.
    """
    del q  # the stub does not read the question. Yours must.
    return load_corpus()[:k]


__all__ = ["search", "load_corpus", "OWNER", "INTERFACE", "STATUS"]
