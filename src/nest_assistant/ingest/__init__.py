"""TEAM 1 — INGEST · *documents in, clean text out*

You own one function::

    build_chunks(src: Path) -> list[Chunk]

Everybody downstream — INDEX, ANSWER, EVAL — receives whatever you return here
and nothing else. If a tier is wrong in your output, it is wrong in the whole
system, and no amount of prompting downstream will fix it.

Your tasks
----------
W1-1.1  Data inventory        -> data/manifest.yaml + data/INVENTORY.md
W1-1.2  Ingestion pipeline    -> this file, for real
W1-1.3  Chunking comparison   -> droppable

Stuck for 15 minutes?
---------------------
Read ``fixtures/manifest.yaml`` and ``tests/test_ingest.py``. The test says
exactly what "working" means. If the question is about what tier a document
should be, that is a policy question — take it to the PM coordinators, not to a
text editor.
"""

from __future__ import annotations

from pathlib import Path

from ..config import corpus_dir
from ..schema import Chunk

OWNER = "TEAM 1 — INGEST"
INTERFACE = "ingest.build_chunks(src: Path) -> list[Chunk]"
STATUS = "stub"  # flip to "real" when you replace the body below. `make board` reads this.


# ---------------------------------------------------------------------------
# TEAM 1 — REPLACE ME
# ---------------------------------------------------------------------------
def build_chunks(src: Path | None = None) -> list[Chunk]:
    """Read every document under ``src`` and return retrievable, citable chunks.

    Contract you must satisfy:

    * Every returned :class:`~nest_assistant.schema.Chunk` has a **stable** id.
      Re-running over an unchanged document produces the same ids, because
      citations made yesterday must still point at the right text today.
    * ``tier`` is inherited from ``manifest.yaml``. A document with no manifest
      entry is **not** ingested as ``public`` — it is not ingested at all, and it
      is reported. Defaulting to public is how a private document leaks.
    * ``source`` is the filename a human would name if they cited it by hand.
    * ``text`` is clean enough to read aloud: no page furniture, no repeated
      headers, no ``\\x0c``.
    * Chunks are small enough to retrieve precisely and large enough to make
      sense alone. Choosing that size is the interesting part of your job —
      write down what you chose and why.

    Args:
        src: directory of documents. Defaults to ``data/`` when it has content,
            otherwise the synthetic ``fixtures/``.

    Returns:
        Chunks, in document order.

    The stub below returns three hand-written chunks so that INDEX, ANSWER,
    EVAL and CHAT all have something to work with before you have written a
    line of code. Delete it.
    """
    src = Path(src) if src is not None else corpus_dir()

    return [
        Chunk(
            id="stub-prezzi#1",
            text=(
                "(STUB) La retta annuale in camera singola è di 10.450 euro, "
                "comprensiva di utenze, pasti dal lunedì al venerdì e percorso formativo. "
                "La camera doppia costa 8.250 euro all'anno."
            ),
            source="stub-prezzi-2026.md",
            tier="public",
            lang="it",
            section="Tariffe",
        ),
        Chunk(
            id="stub-regolamento#1",
            text=(
                "(STUB) Il silenzio è richiesto dalle 23:00 alle 07:00 nei giorni feriali "
                "e dalle 24:00 alle 09:00 nel fine settimana. Gli ospiti esterni devono "
                "essere annunciati alla reception entro le 20:00."
            ),
            source="stub-regolamento.md",
            tier="resident",
            lang="it",
            section="Convivenza",
        ),
        Chunk(
            id="stub-procedure#1",
            text=(
                "(STUB) In caso di morosità superiore a due mensilità la segreteria invia "
                "un sollecito formale e informa la direzione entro cinque giorni lavorativi."
            ),
            source="stub-procedure-segreteria.md",
            tier="staff",
            lang="it",
            section="Amministrazione",
        ),
    ]


__all__ = ["build_chunks", "OWNER", "INTERFACE", "STATUS"]
