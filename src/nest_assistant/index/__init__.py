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
``tests/test_components.py`` has a skipped test named
``test_public_never_sees_private``. Unskip it. It is your definition of done.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..config import CHUNKS_PATH, DEFAULT_K, EMBEDDING_MODEL, INDEX_DIR, embedding_model_cached
from ..ingest import build_chunks
from ..schema import Chunk, Tier, tier_allows
from ..storage import read_chunks

if TYPE_CHECKING:
    import numpy as np

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
# The vector index: one row of numbers per chunk, saved under build/index/
# ---------------------------------------------------------------------------

EMBEDDINGS_PATH = INDEX_DIR / "embeddings.npy"
META_PATH = INDEX_DIR / "meta.json"

_model: Any = None
_cache: dict[str, Any] = {}  # fingerprint -> (vectors, chunk_ids), for this process


def _fingerprint(chunks: list[Chunk], model: str) -> str:
    """A seal over everything that changes a vector: the model, and each id and text.

    One changed comma, one new chunk or a different model gives a different seal,
    which is how :func:`build_index` knows the saved index is stale. ``tier`` is
    left out on purpose: it does not change a vector, and the saved index never
    supplies it — tiers always come from the live corpus.
    """
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    for chunk in chunks:
        h.update(b"\x00" + chunk.id.encode("utf-8") + b"\x00" + chunk.text.encode("utf-8"))
    return h.hexdigest()


def _embed(texts: list[str]) -> np.ndarray:
    """Turn texts into unit-length vectors, so closeness is a single dot product."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed — run `make setup`"
            ) from None
        if not embedding_model_cached():
            raise RuntimeError(f"{EMBEDDING_MODEL} is not downloaded — run `make warm`")
        _model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
    vectors = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.astype("float32")


def build_index(
    chunks: list[Chunk] | None = None, force: bool = False
) -> tuple[np.ndarray, list[str]]:
    """Vectors for every chunk, from ``build/index/`` if still valid, else freshly embedded.

    Returns ``(vectors, chunk_ids)``: row ``i`` of ``vectors`` belongs to
    ``chunk_ids[i]``. Only vectors and ids are saved — never text or tier — so a
    stale file on disk cannot hand anyone an out-of-date tier.
    """
    import numpy as np

    chunks = load_corpus() if chunks is None else chunks
    fingerprint = _fingerprint(chunks, EMBEDDING_MODEL)

    if not force and fingerprint in _cache:
        return _cache[fingerprint]

    if not force and META_PATH.exists() and EMBEDDINGS_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        if meta.get("fingerprint") == fingerprint:
            _cache[fingerprint] = (np.load(EMBEDDINGS_PATH), meta["chunk_ids"])
            return _cache[fingerprint]

    vectors = _embed([chunk.text for chunk in chunks])
    ids = [chunk.id for chunk in chunks]
    meta = {
        "fingerprint": fingerprint,
        "model": EMBEDDING_MODEL,
        "dim": int(vectors.shape[1]),
        "n_chunks": len(ids),
        "chunk_ids": ids,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    # Write to a temporary name, then rename: a crash halfway never leaves a
    # half-written index that looks valid. meta.json goes last, because it is
    # what says "this index is complete".
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    tmp_vectors = EMBEDDINGS_PATH.with_suffix(".tmp.npy")
    np.save(tmp_vectors, vectors)
    os.replace(tmp_vectors, EMBEDDINGS_PATH)
    tmp_meta = META_PATH.with_suffix(".tmp")
    tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_meta, META_PATH)

    _cache[fingerprint] = (vectors, ids)
    return _cache[fingerprint]


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

    Scores are cosine similarities, roughly 0..1: see :func:`search_with_scores`.
    """
    return [chunk for chunk, _ in search_with_scores(q, tier, k)]


def search_with_scores(
    q: str, tier: Tier = "public", k: int = DEFAULT_K
) -> list[tuple[Chunk, float]]:
    """:func:`search`, with each chunk's similarity to ``q``.

    The score is the cosine similarity between question and chunk: 1.0 would be
    identical meaning, around 0.2 is "unrelated". On the fixtures a right answer
    usually scores 0.35–0.65; below ~0.3 treat the top result as a guess.
    """
    # Tier filter first, before any ranking: a chunk the caller may not see is
    # never scored, so it can never be returned — whatever the ranking does.
    corpus = load_corpus()
    allowed = [i for i, chunk in enumerate(corpus) if tier_allows(tier, chunk.tier)]
    if not allowed or k <= 0:
        return []

    try:
        vectors, _ = build_index(corpus)
        query = _embed([q])[0]
    except (ImportError, RuntimeError):
        # `make setup-lite` or CI: no embedding model. Stay safe and runnable —
        # tier-filtered, in document order — rather than break the pipeline.
        return [(corpus[i], 0.0) for i in allowed[:k]]

    scores = vectors[allowed] @ query
    # Stable sort on the negated score: ties keep document order, so the same
    # query over the same corpus always ranks the same way.
    order = (-scores).argsort(kind="stable")[:k]
    return [(corpus[allowed[i]], float(scores[i])) for i in order]


__all__ = [
    "search",
    "search_with_scores",
    "load_corpus",
    "build_index",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
