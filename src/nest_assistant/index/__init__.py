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

How it works
------------
One vector index over the whole corpus, saved under ``build/index/``. A search
first drops every chunk the caller may not see, then ranks only what is left:
meaning (cosine similarity) picks the best five, and keywords (BM25) re-order
them so exact words and numbers rise. A forbidden chunk is never scored, so no
ranking bug can return it. The design, its measurements and its trade-offs are
in docs/INDEX.md.

There is a second filter downstream in ``pipeline.py``. It is not our safety
net: defence in depth means two independent layers that both work.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from ..config import CHUNKS_PATH, DEFAULT_K, EMBEDDING_MODEL, INDEX_DIR, embedding_model_cached
from ..ingest import build_chunks
from ..schema import Chunk, Tier, tier_allows, tier_rank
from ..storage import read_chunks

if TYPE_CHECKING:
    import numpy as np

OWNER = "TEAM 2 — INDEX"
INTERFACE = "index.search(q: str, tier: Tier, k: int) -> list[Chunk]"
STATUS = "real"  # `make board` reads this.


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


def _prefixes(model: str) -> dict[str, str]:
    """What the model expects before a question and before a passage.

    E5 models were trained on ``"query: …"`` against ``"passage: …"`` and rank
    measurably worse without them. Other models take the text as it is.
    """
    if "e5" in model.lower():
        return {"query": "query: ", "passage": "passage: "}
    return {"query": "", "passage": ""}


def _embed(texts: list[str], kind: Literal["query", "passage"] = "query") -> np.ndarray:
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
    prefix = _prefixes(EMBEDDING_MODEL)[kind]
    vectors = _model.encode(
        [prefix + text for text in texts], normalize_embeddings=True, show_progress_bar=False
    )
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

    vectors = _embed([chunk.text for chunk in chunks], "passage")
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

    Meaning finds the candidates, keywords sharpen their order: see
    :func:`search_with_scores` and docs/INDEX.md.
    """
    return [chunk for chunk, _ in search_with_scores(q, tier, k, "hybrid")]


Method = Literal["hybrid", "vector", "keyword"]


def search_with_scores(
    q: str, tier: Tier = "public", k: int = DEFAULT_K, method: Method = "hybrid"
) -> list[tuple[Chunk, float]]:
    """:func:`search`, with each chunk's score. ``method`` picks the ranking.

    ``"vector"``: cosine similarity between question and chunk. With e5-small
    almost everything lands between 0.78 and 0.90: the order is meaningful, the
    absolute value is not a refusal signal (see docs/INDEX.md).

    ``"keyword"``: BM25 over the words of question and chunk. 0 means no word in
    common; there is no upper bound.

    ``"hybrid"`` (what :func:`search` uses): meaning picks the top
    :data:`RERANK_DEPTH`, keywords re-order them, fused by position
    (:func:`_fuse`). The score only orders results; it is not comparable with
    the other two.

    With no embedding model installed every method falls back to ``"keyword"``.
    """
    tier_rank(tier)  # an unknown caller tier is a bug upstream: fail loudly, show nothing
    # Tier filter first, before any ranking: a chunk the caller may not see is
    # never scored, so it can never be returned — whatever the ranking does.
    corpus = load_corpus()
    allowed = [i for i, chunk in enumerate(corpus) if _visible(chunk, tier)]
    if not allowed or k <= 0:
        return []

    keyword = _rank_keyword(q, corpus, allowed)
    if method == "keyword":
        ranked = keyword
    else:
        try:
            vector = _rank_vector(q, corpus, allowed)
        except (ImportError, RuntimeError):
            # `make setup-lite` or CI: no embedding model. Keywords need nothing
            # installed, so rank by those rather than break the pipeline.
            vector = None
        if vector is None:
            ranked = keyword
        elif method == "vector":
            ranked = vector
        else:
            # A chunk sharing no word with the question has no keyword evidence;
            # its place in that list is document order, i.e. noise. Leave it out.
            # Keywords only re-order meaning's top RERANK_DEPTH: they can promote
            # an exact match (a price, "cena comunitaria") but never push a chunk
            # out of what ANSWER reads, nor pull in one meaning did not pick.
            # A chunk sharing no word with the question has no keyword evidence.
            head = {i for i, _ in vector[:RERANK_DEPTH]}
            matched = [(i, score) for i, score in keyword if score > 0 and i in head]
            ranked = _fuse([vector, matched], [1.0, KEYWORD_WEIGHT], FUSION_K)

    results = [(corpus[i], score) for i, score in ranked[:k]]

    # Belt and braces, still inside INDEX: if a future change to the ranking ever
    # mixes up positions, fail closed (the pipeline turns this into a refusal)
    # rather than hand anyone a chunk above their tier.
    if any(not _visible(chunk, tier) for chunk, _ in results):
        raise RuntimeError("index returned a chunk above the caller's tier")
    return results


def _rank_vector(q: str, corpus: list[Chunk], allowed: list[int]) -> list[tuple[int, float]]:
    """``allowed`` corpus positions, best first, scored by cosine similarity to ``q``."""
    vectors, _ = build_index(corpus)
    scores = vectors[allowed] @ _embed([q], "query")[0]
    # Stable sort on the negated score: ties keep document order, so the same
    # query over the same corpus always ranks the same way.
    order = (-scores).argsort(kind="stable")
    return [(allowed[i], float(scores[i])) for i in order]


# ---------------------------------------------------------------------------
# Keyword ranking: BM25, in plain Python so it runs with nothing installed
# ---------------------------------------------------------------------------

_WORD = re.compile(r"\d+(?:[.,:/]\d+)*|\w+")
"""A number with its separators stays one token (10.450, 23:00, 31/07): those
are exactly the tokens embeddings blur and a resident types verbatim."""

_token_cache: dict[str, list[list[str]]] = {}  # corpus fingerprint -> tokens per chunk


_STOPWORDS = frozenset(
    """a ad al alla alle allo agli ai anche che chi ci con cosa come da dal dalla
    dei del della delle dello degli di e ed gli ha ho i il in io la le lo ma mi
    ne nei nel nella non o per piu puo se si sia sono su sul sulla ti tra tu un
    una uno vi
    an and are at be by can do does for from how i in is it of on or the to what
    when where which who will with you your""".split()
)
"""Words that match everywhere and therefore mean nothing, Italian and English."""


def _tokens(text: str) -> list[str]:
    """Words of ``text``, normalised so that the way a resident types still matches.

    Accents are dropped (``puo`` matches ``può``), stopwords removed, and longer
    words lose their final vowel so ``singola``, ``singole`` and ``singoli`` are
    one word. Crude next to a real stemmer, but it is twelve characters of code
    and Italian inflects mostly in the last vowel.
    """
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    words = []
    for word in _WORD.findall(plain):
        if word in _STOPWORDS:
            continue
        if len(word) > 4 and word[-1] in "aeio" and not word[0].isdigit():
            word = word[:-1]
        words.append(word)
    return words


def _bm25(query: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Okapi BM25 score of every doc for ``query``.

    A word counts more when it is rare across the docs (``idf``), with
    diminishing returns for repeating it (``k1``), and long docs are not
    rewarded just for being long (``b``).
    """
    n = len(docs)
    avg_len = sum(map(len, docs)) / n or 1.0
    terms = set(query)
    df = {t: sum(t in doc for doc in map(set, docs)) for t in terms}
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}
    scores = []
    for doc in docs:
        tf = {t: doc.count(t) for t in terms}
        norm = k1 * (1 - b + b * len(doc) / avg_len)
        scores.append(sum(idf[t] * tf[t] * (k1 + 1) / (tf[t] + norm) for t in terms if tf[t]))
    return scores


def _rank_keyword(q: str, corpus: list[Chunk], allowed: list[int]) -> list[tuple[int, float]]:
    """``allowed`` corpus positions, best first, scored by BM25 against ``q``.

    Word statistics are computed over the allowed chunks only, so what a caller
    may not see cannot even nudge their scores.
    """
    key = _fingerprint(corpus, "keyword")
    if key not in _token_cache:
        _token_cache[key] = [_tokens(chunk.text) for chunk in corpus]
    tokens = _token_cache[key]
    scores = _bm25(_tokens(q), [tokens[i] for i in allowed])
    order = sorted(range(len(allowed)), key=lambda j: -scores[j])  # stable: ties keep doc order
    return [(allowed[j], scores[j]) for j in order]


KEYWORD_WEIGHT = 0.5
"""How much the keyword ranking counts in the fusion, with meaning counting 1.
Chosen on the fixtures, checked on the real documents: docs/INDEX.md, W1-2.3."""

FUSION_K = 2
"""The ``k`` in reciprocal rank fusion: how quickly a lower position loses weight.
The paper's 60 suits long lists; within five candidates it makes 1st and 5th
nearly equal (1/61 vs 1/65), so keywords could hardly re-order anything."""

RERANK_DEPTH = 5
"""Keywords may re-order only this many of meaning's best chunks. Equal to the
``k`` ANSWER reads, so the chunks it gets are exactly meaning's top 5."""


def _fuse(
    rankings: list[list[tuple[int, float]]], weights: list[float], k: int = 60
) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: each ranking gives a chunk ``weight / (k + position)``.

    Positions, not scores, because cosine (0.78–0.90) and BM25 (0 to anything)
    are not on the same scale. ``k = 60`` is the value from the original paper
    (Cormack et al., 2009): it stops first place in one list from outweighing
    good places in both.
    """
    fused: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for position, (i, _) in enumerate(ranking, start=1):
            fused[i] = fused.get(i, 0.0) + weight / (k + position)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))  # ties: doc order


def _visible(chunk: Chunk, tier: Tier) -> bool:
    """May a caller at ``tier`` see ``chunk``? A chunk with a broken tier label is hidden."""
    try:
        return tier_allows(tier, chunk.tier)
    except ValueError:
        return False


__all__ = [
    "search",
    "search_with_scores",
    "load_corpus",
    "build_index",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
