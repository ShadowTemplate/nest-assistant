"""The command line. Every ``make`` target is a thin wrapper around this.

Two entry points for the same commands, on purpose::

    make demo                 # what the README tells you to type
    uv run nest demo          # what to type when make is not available (Windows)
"""

from __future__ import annotations

import argparse
import sys
from importlib import import_module

from .config import CHUNKS_PATH, corpus_dir, ensure_build_dir, load_dotenv
from .schema import TIERS

# The progress board. `make board` prints this, and the PM coordinators copy it
# onto the whiteboard at 12:25 and 15:15.
COMPONENTS = [
    ("INGEST", "nest_assistant.ingest", "TEAM 1"),
    ("INDEX", "nest_assistant.index", "TEAM 2"),
    ("ANSWER", "nest_assistant.answer", "TEAM 3"),
    ("IDENTITY", "nest_assistant.identity", "TEAM 4"),
    ("BOT", "nest_assistant.bot", "TEAM 4"),
    ("EVAL", "nest_assistant.evaluate", "TEAM 5"),
    ("GUARDRAILS", "nest_assistant.guardrails", "TEAM 5"),
]

DEMO_QUESTIONS = [
    ("Quanto costa una camera singola?", "public"),
    ("A che ora è il silenzio la sera?", "resident"),
    ("Posso tenere un gatto in camera?", "public"),
]


def cmd_demo(args: argparse.Namespace) -> int:
    """Ask the assistant a few questions, end to end.

    Works on a freshly cloned repo with no API key, no data and no internet.
    That property is the whole reason six teams can work in parallel — if you
    ever break it, you have broken the workshop, not just a test.
    """
    from .pipeline import Pipeline

    pipeline = Pipeline()
    questions = [(args.question, args.tier)] if args.question else DEMO_QUESTIONS

    for question, tier in questions:
        answer = pipeline.ask(question, tier)
        print(f"\n\033[1m[{tier}]\033[0m {question}")
        print(f"  → {answer.text}")
        if answer.citations:
            print(f"  fonti: {', '.join(answer.citations)}")
        print(f"  refused={answer.refused} confidence={answer.confidence:.2f}")
    print()
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Build ``chunks.jsonl`` from the corpus."""
    from .ingest import build_chunks
    from .storage import write_chunks

    src = corpus_dir()
    print(f"reading documents from {src}")
    chunks = build_chunks(src)
    ensure_build_dir()
    n = write_chunks(chunks, CHUNKS_PATH)
    print(f"wrote {n} chunks to {CHUNKS_PATH}")

    by_tier: dict[str, int] = {}
    for chunk in chunks:
        by_tier[chunk.tier] = by_tier.get(chunk.tier, 0) + 1
    for tier in TIERS:
        print(f"  {tier:<9} {by_tier.get(tier, 0)}")
    if src.name == "fixtures":
        print("\nnote: this is the SYNTHETIC corpus. Real documents go in data/.")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search the index directly — useful when debugging bad answers."""
    from .index import search

    results = search(args.question, args.tier, args.k)
    if not results:
        print("no results")
        return 0
    for i, chunk in enumerate(results, start=1):
        print(f"\n{i}. [{chunk.id}] tier={chunk.tier} source={chunk.source}")
        print(f"   {chunk.text[:200]}{'…' if len(chunk.text) > 200 else ''}")
    print()
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Score the whole system and print the card."""
    from . import evaluate
    from .pipeline import Pipeline

    scorecard = evaluate.run(Pipeline())
    print()
    print(scorecard.summary())
    print()
    if args.save:
        print(f"saved to {evaluate.save(scorecard, args.label)}")
    return 0 if scorecard.tier_leaks == 0 else 1


def cmd_bot(args: argparse.Namespace) -> int:
    """Start the bot (console until TEAM 4 lands Telegram)."""
    from .bot import run

    run()
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    """Which stubs have been replaced with real implementations.

    This is TEAM 6's progress board (W1-6.2). It reads ``STATUS`` from each
    component, so it cannot lie about what has landed and what has not.
    """
    print()
    print("  COMPONENT    OWNER     STATUS")
    print("  " + "-" * 40)
    real = 0
    for name, module_path, owner in COMPONENTS:
        module = import_module(module_path)
        status = getattr(module, "STATUS", "unknown")
        mark = "\033[32mREAL\033[0m" if status == "real" else "\033[33mSTUB\033[0m"
        real += status == "real"
        print(f"  {name:<12} {owner:<9} {mark}")
    print("  " + "-" * 40)
    print(f"  {real}/{len(COMPONENTS)} real\n")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """The pre-work check. Prints ✅ and a code to post in #setup.

    Deliberately does not need an API key, the internet, or any Nest data.
    """
    import platform

    ok = True
    print()
    print("  Nest Assistant — environment check")
    print("  " + "-" * 40)

    version = sys.version_info
    py_ok = (version.major, version.minor) >= (3, 12)
    ok &= py_ok
    mark = "✅" if py_ok else "❌ need 3.12+"
    print(f"  python {version.major}.{version.minor}.{version.micro:<10} {mark}")

    try:
        from .pipeline import Pipeline

        answer = Pipeline().ask("Quanto costa una camera singola?", "public")
        pipeline_ok = bool(answer.text)
        print(f"  pipeline{'':<13} {'✅' if pipeline_ok else '❌'}")
        ok &= pipeline_ok
    except Exception as exc:  # noqa: BLE001 - this is the diagnostic
        ok = False
        print(f"  pipeline{'':<13} ❌ {exc}")

    try:
        import yaml  # noqa: F401

        print(f"  dependencies{'':<9} ✅")
    except ImportError:
        ok = False
        print(f"  dependencies{'':<9} ❌ run `make setup`")

    print("  " + "-" * 40)
    if ok:
        code = f"NEST-{platform.system()[:3].upper()}-{version.major}{version.minor}-OK"
        print(f"\n  ✅ Tutto a posto. Posta questo codice in #setup:\n\n      {code}\n")
        return 0
    print("\n  ❌ Something is wrong. Post the output above in #setup.\n")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nest", description="Nest Assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", help="ask the assistant a question, end to end")
    p.add_argument("question", nargs="?", help="defaults to three sample questions")
    p.add_argument("--tier", choices=TIERS, default="public")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("ingest", help="build chunks.jsonl from the corpus")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search", help="query the index directly")
    p.add_argument("question")
    p.add_argument("--tier", choices=TIERS, default="public")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("eval", help="score the system against eval/questions.yaml")
    p.add_argument("--save", action="store_true", help="write a dated scorecard")
    p.add_argument("--label", default="", help="suffix for the results filename")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("bot", help="start the chat bot")
    p.set_defaults(func=cmd_bot)

    p = sub.add_parser("board", help="which stubs are still stubs")
    p.set_defaults(func=cmd_board)

    p = sub.add_parser("check", help="verify the environment (pre-work)")
    p.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252, which cannot print "→" or Italian
    # answers with curly quotes. Force UTF-8 so the demo works on every laptop.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
