"""Paths and settings. One place, so nobody hardcodes a path in six modules.

Nothing here reads a secret at import time — secrets are read where they are
used, so that the whole pipeline still imports and runs with no ``.env`` at all.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
"""Repository root."""

DATA_DIR = Path(os.environ.get("NEST_DATA_DIR", ROOT / "data"))
"""Real Nest documents. **Gitignored. Never committed.** See docs/DATA_POLICY.md."""

FIXTURES_DIR = ROOT / "fixtures"
"""Synthetic, invented, Nest-*like* documents. Committed on purpose: they are
what the public repository shows the world, and they let every team work before
the real corpus arrives."""

BUILD_DIR = Path(os.environ.get("NEST_BUILD_DIR", ROOT / "build"))
"""Generated artefacts: chunks.jsonl, the vector index, scorecards. Gitignored."""

CHUNKS_PATH = BUILD_DIR / "chunks.jsonl"
INDEX_DIR = BUILD_DIR / "index"
EVAL_DIR = ROOT / "eval"
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "eval" / "results"

# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------


NOT_DOCUMENTS = {
    "manifest.yaml",
    "INVENTORY.md",
    "README.md",
    "allowlist.json",
    "bot_testers.json",
    ".gitkeep",
}
"""Files that sit at the top of ``data/`` next to the documents but are not documents.
Shared with INGEST, so ``data/`` counts as a corpus exactly when ingest would find
something in it."""


def is_document(path: Path, root: Path) -> bool:
    """True for a file under ``root`` that is a candidate document.

    The names in ``NOT_DOCUMENTS`` are only skipped at the top level, so a
    ``staff/README.md`` listed in the manifest is still read. Anything inside a
    hidden folder (``.git``, ``.cache``) or with a hidden name is skipped.
    """
    rel = path.relative_to(root)
    return (
        path.is_file()
        and not (len(rel.parts) == 1 and rel.name in NOT_DOCUMENTS)
        and not any(part.startswith(".") for part in rel.parts)
    )


def corpus_dir() -> Path:
    """Where documents are read from.

    ``data/`` if it holds real documents, otherwise the synthetic ``fixtures/``.
    This is why a student with no access to the real corpus can still do every
    task on the list, and why nothing anyone writes should care which one it got.
    """
    if DATA_DIR.exists() and any(is_document(p, DATA_DIR) for p in DATA_DIR.rglob("*")):
        return DATA_DIR
    return FIXTURES_DIR


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

ANSWER_MODEL = os.environ.get("NEST_ANSWER_MODEL", "claude-sonnet-5-5")
"""The hosted model ANSWER generates with (pair 1).

In October 2027 this line, and only this line, becomes a self-hosted model. If
swapping it turns out to need changes anywhere else, an interface was dishonest.

Cost knob: each team has a hard monthly spend limit, and Sonnet is the default
so it lasts the day. ``NEST_ANSWER_MODEL=claude-haiku-4-5`` in ``.env`` is
cheaper still, ``claude-opus-5-5`` is stronger and dearer — and measuring what
either costs you in answer quality with `make eval` is a better afternoon than
arguing about it.
"""

JUDGE_MODEL = os.environ.get("NEST_JUDGE_MODEL", "claude-opus-5-5")
"""The model EVAL uses as a judge. Deliberately named separately from
ANSWER_MODEL: a model grading its own homework is a known problem, and being
able to point them at different models is how you check for it.

Stronger than the answer model on purpose: spotting a claim the retrieved chunks
do not support is the hard part of judging, and the judge runs only during
``make eval``, so the extra cost is small. **Keep it fixed.** October's and
March's scorecards are only comparable if the same judge graded both — changing
the judge changes the ruler, not the system."""

EMBEDDING_MODEL = os.environ.get("NEST_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
"""TEAM 2's choice: multilingual, trained on short question → answering passage.

Measured against the starting model (paraphrase-multilingual-MiniLM-L12-v2) and
an English-first one (all-MiniLM-L6-v2): the right chunk ranked first went from
53% to 65% on the real documents and from 53% to 93% on the fixtures, while the
English-first model managed 29% and 40%. Numbers and method in docs/INDEX.md.
E5 models need ``"query: "`` / ``"passage: "`` prefixes — ``index`` adds them.
"""


def embedding_model_cached(model: str | None = None) -> bool:
    """True if the embedding model is already in the local Hugging Face cache.

    Checks the folder on disk without importing anything heavy, so
    ``make check`` can warn about a missing model in under a second.
    """
    model = model or EMBEDDING_MODEL
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.join(Path.home(), ".cache", "huggingface"), "hub"
    )
    snapshots = Path(hub) / f"models--{model.replace('/', '--')}" / "snapshots"
    return snapshots.is_dir() and any(snapshots.iterdir())


CONTEXT_WINDOW_MINUTES = int(os.environ.get("NEST_CONTEXT_MINUTES", "10"))
"""TEAM 4 — how long a conversation stays "the same conversation". Messages older
than this are not shown to the question rewriter. See ``bot/context.py``."""

CONTEXT_MAX_TURNS = int(os.environ.get("NEST_CONTEXT_TURNS", "4"))
"""TEAM 4 — at most this many recent exchanges go into the rewriter's prompt."""

DEFAULT_K = int(os.environ.get("NEST_K", "5"))
DEFAULT_LANG = os.environ.get("NEST_LANG", "it")

# ---------------------------------------------------------------------------
# Secrets — read lazily, never logged
# ---------------------------------------------------------------------------


def anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def telegram_bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def load_dotenv(path: Path | None = None) -> None:
    """Minimal ``.env`` loader, so we do not add a dependency for six lines.

    Existing environment variables win, which is what you want when a student
    exports a key in their shell to test something.
    """
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_build_dir() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return BUILD_DIR
