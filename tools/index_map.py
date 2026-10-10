"""TEAM 2 — a visual map of the index, for deciding what to do next.

    uv run python tools/index_map.py          # writes build/index-map.html

Every chunk is a dot, coloured by tier; every question in eval/questions.yaml is
a ring, joined to the chunk it ranked first. Hover a ring to see its top 5.
Below the map: top-1 scores split by outcome (where a "this is a guess"
threshold could go) and one row per question.

The map squeezes 384 dimensions into 2 (PCA), so closeness on screen is only
approximate — the scores in the tooltips and the table are the real ones.

The page holds chunk text, so it is written under build/ (gitignored) and must
never be committed: on data/ that text is Nest's.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import numpy as np

from nest_assistant import evaluate, index
from nest_assistant.config import BUILD_DIR, EMBEDDING_MODEL, corpus_dir
from nest_assistant.schema import tier_allows

OUT = BUILD_DIR / "index-map.html"
TEMPLATE = Path(__file__).with_name("index_map.html")
TOP = 5


def main() -> int:
    corpus = index.load_corpus()
    vectors, _ = index.build_index(corpus)
    questions = evaluate.load_questions()
    qvecs = (
        index._embed([q["question"] for q in questions], "query") if questions else np.zeros((0, 1))
    )

    # PCA: the two directions along which the chunks differ most.
    mean = vectors.mean(axis=0)
    _, s, vt = np.linalg.svd(vectors - mean, full_matrices=False)
    axes = vt[:2].T
    explained = float((s[:2] ** 2).sum() / (s**2).sum())
    cxy = (vectors - mean) @ axes
    qxy = (qvecs - mean) @ axes if questions else np.zeros((0, 2))

    chunks = [
        {
            "id": c.id,
            "source": c.source,
            "tier": c.tier,
            "section": c.section or "",
            "text": c.text[:220],
            "x": float(cxy[i, 0]),
            "y": float(cxy[i, 1]),
        }
        for i, c in enumerate(corpus)
    ]
    rows = []
    for j, item in enumerate(questions):
        tier = item.get("tier", "public")
        allowed = [i for i, c in enumerate(corpus) if tier_allows(tier, c.tier)]
        scores = vectors[allowed] @ qvecs[j]
        order = [allowed[i] for i in (-scores).argsort(kind="stable")]
        score_of = {allowed[i]: float(scores[i]) for i in range(len(allowed))}
        expected = item.get("expected_sources") or []
        first_right = next(
            (r for r, i in enumerate(order, 1) if corpus[i].source in expected), None
        )
        rows.append(
            {
                "id": item.get("id", ""),
                "question": item["question"],
                "tier": tier,
                "expect": item.get("expect", "answer"),
                "expected": expected,
                "top": [{"i": i, "score": score_of[i]} for i in order[:TOP]],
                "first_right": first_right,
                "x": float(qxy[j, 0]),
                "y": float(qxy[j, 1]),
            }
        )

    data = {
        "chunks": chunks,
        "questions": rows,
        "model": EMBEDDING_MODEL,
        "corpus": str(corpus_dir().name),
        "explained": explained,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__DATA__", payload)
        .replace("__MODEL__", html.escape(EMBEDDING_MODEL)),
        encoding="utf-8",
    )
    print(f"wrote {OUT}  ({len(chunks)} chunks, {len(rows)} questions)")
    print("open it in a browser. It contains document text: never commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
