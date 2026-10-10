"""TEAM 2 — measure how well each ranking method finds the right chunk.

    uv run python tools/retrieval_report.py --label "vector baseline"
    uv run python tools/retrieval_report.py --html     # draw every saved run

EVAL's hit rate asks "did any of the top 5 come from the right document?", which
is generous when a corpus has six documents. This asks the stricter question:
where did the chunk that holds the answer land?

A question's *right chunk* is one from an ``expected_sources`` document that
contains its ``expected_answer``. Every run is appended to
``build/retrieval-runs.jsonl`` with its label, so the HTML report shows how each
change moved the numbers. Both files live under build/ (gitignored): the report
quotes chunk ids, and on data/ the run file is about Nest's documents.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from nest_assistant import evaluate, index
from nest_assistant.config import BUILD_DIR, EMBEDDING_MODEL, corpus_dir
from nest_assistant.schema import TIERS, tier_allows

RUNS = BUILD_DIR / "retrieval-runs.jsonl"
OUT = BUILD_DIR / "retrieval-report.html"
TEMPLATE = Path(__file__).with_name("retrieval_report.html")

SPELLINGS = {"31 luglio": r"31 luglio|31/0?7"}
"""The same fact written another way in a document. Add to this when a right
chunk is missed only because of how the fact is spelled, never to rescue a
method that ranks badly."""


def right_chunks(question: dict, corpus: list) -> set[str]:
    expected = str(question.get("expected_answer", "")).lower()
    if question.get("expect") == "refusal" or not expected:
        return set()
    pattern = SPELLINGS.get(expected, re.escape(expected))
    sources = question.get("expected_sources") or []
    return {c.id for c in corpus if c.source in sources and re.search(pattern, c.text.lower())}


def measure(method: str, questions: list[dict], corpus: list) -> dict:
    present = {c.source for c in corpus}
    rows, latencies, leaks = [], [], 0
    for q in questions:
        t = time.perf_counter()
        ranked = index.search_with_scores(q["question"], q["tier"], len(corpus), method)
        latencies.append(time.perf_counter() - t)
        ids = [c.id for c, _ in ranked]
        right = right_chunks(q, corpus)
        sources = q.get("expected_sources") or []
        rows.append(
            {
                "id": q["id"],
                "question": q["question"],
                "tier": q["tier"],
                "expect": q.get("expect", "answer"),
                "scored": bool(right) and bool(set(sources) & present),
                "rank": next((r for r, i in enumerate(ids, 1) if i in right), None),
                "doc_rank": next(
                    (r for r, (c, _) in enumerate(ranked, 1) if c.source in sources), None
                ),
                "top": [[c.id, round(s, 4)] for c, s in ranked[:3]],
            }
        )
        for tier in TIERS:
            hits = index.search_with_scores(q["question"], tier, len(corpus), method)
            leaks += sum(not tier_allows(tier, c.tier) for c, _ in hits)

    scored = [r for r in rows if r["scored"]]
    n = len(scored) or 1
    ranks = [r["rank"] for r in scored]
    return {
        "method": method,
        "n_scored": len(scored),
        "piece_1st": sum(r == 1 for r in ranks) / n,
        "piece_top3": sum(r <= 3 for r in ranks) / n,
        "piece_top5": sum(r <= 5 for r in ranks) / n,  # what ANSWER reads at k=5
        "mrr": sum(1 / r for r in ranks) / n,
        "doc_1st": sum(r["doc_rank"] == 1 for r in scored) / n,
        "leaks": leaks,
        "ms_max": max(latencies) * 1000,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="", help="what changed since the last run")
    parser.add_argument("--methods", default="vector", help="comma-separated, e.g. vector,hybrid")
    parser.add_argument("--questions", choices=["auto", "fixtures", "data"], default="auto")
    parser.add_argument("--corpus-name", default="", help='e.g. "Real documents, Team 1 chunks"')
    parser.add_argument("--html", action="store_true", help="only draw the report from saved runs")
    parser.add_argument(
        "--also",
        nargs="*",
        default=[],
        type=Path,
        help="more run files to draw, e.g. the fixtures'",
    )
    args = parser.parse_args()

    if args.html:
        return draw([RUNS, *args.also])

    which = args.questions
    if which == "auto":
        which = "data" if corpus_dir().name == "data" else "fixtures"
    questions = evaluate.load_questions(corpus=which)
    corpus = index.load_corpus()
    index.search_with_scores("warm up", "staff", 1)  # load the model outside the timings

    print(f"\n{args.label or '(no label)'} — {len(corpus)} chunks, {which} questions\n")
    print(
        f"  {'method':<10}{'right 1st':>11}{'top 3':>8}{'top 5':>8}{'MRR':>7}"
        f"{'doc 1st':>9}{'leaks':>7}{'ms':>6}"
    )
    stamp = datetime.now().isoformat(timespec="seconds")
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a", encoding="utf-8") as fh:
        for method in args.methods.split(","):
            m = measure(method.strip(), questions, corpus)
            print(
                f"  {m['method']:<10}{m['piece_1st']:>11.0%}{m['piece_top3']:>8.0%}"
                f"{m['piece_top5']:>8.0%}{m['mrr']:>7.2f}{m['doc_1st']:>9.0%}"
                f"{m['leaks']:>7}{m['ms_max']:>6.0f}"
            )
            run = {"label": args.label, "at": stamp, "questions": which, "chunks": len(corpus)}
            run["corpus"] = args.corpus_name or f"{which} ({len(corpus)} chunks)"
            run |= {"model": EMBEDDING_MODEL, **m}
            fh.write(json.dumps(run, ensure_ascii=False) + "\n")
    print(f"\n  ({m['n_scored']} questions with a known right chunk; saved to {RUNS})\n")
    return 0


def draw(paths: list[Path]) -> int:
    runs = []
    for path in paths:
        if not path.exists():
            print(f"no runs in {path}")
            return 1
        runs += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for run in runs:
        run.setdefault("corpus", f"{run['questions']} ({run['chunks']} chunks)")
        # runs saved before top 5 was measured: their per-question ranks hold it
        if "piece_top5" not in run:
            ranks = [row["rank"] for row in run["rows"] if row["scored"]]
            run["piece_top5"] = sum(r <= 5 for r in ranks) / (len(ranks) or 1)
    payload = json.dumps(runs, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)
    OUT.write_text(page.replace("__WHERE__", html.escape(str(BUILD_DIR))), encoding="utf-8")
    print(f"wrote {OUT} ({len(runs)} runs). It quotes chunk ids: never commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
