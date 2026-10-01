"""Nest Assistant — an AI assistant for the Nest student residence, Trento.

Built by students, one workshop at a time. Start with ``docs/ARCHITECTURE.md``.

The six components and who owns them::

    ingest    TEAM 1   documents in, clean text out
    index     TEAM 2   text in, relevant text out
    answer    TEAM 3   retrieved text in, trustworthy Italian out
    identity  TEAM 4   who is asking
    bot       TEAM 4   the part everyone can see
    evaluate  TEAM 5   how do we know it works
    (seams)   TEAM 6   hooks, CI, the checkpoint

They are held together by ``schema.py`` (the contracts) and ``pipeline.py`` (the
wiring). Everything else is replaceable — that is the point.
"""

__version__ = "0.1.0"

from .schema import Answer, Chunk, Scorecard, Tier

__all__ = ["Answer", "Chunk", "Scorecard", "Tier", "__version__"]
