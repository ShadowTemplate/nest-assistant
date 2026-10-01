"""Reading and writing ``chunks.jsonl``.

Shared plumbing, owned by nobody in particular. INGEST writes the file, INDEX
reads it. One line of JSON per chunk, because that format survives being opened
in a text editor at 15:00 by somebody trying to work out what went wrong.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .schema import Chunk


def write_chunks(chunks: Iterable[Chunk], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_chunks(path: Path) -> list[Chunk]:
    if not path.exists():
        return []
    chunks: list[Chunk] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(Chunk.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError(f"{path}:{line_no} is not a valid Chunk: {exc}") from exc
    return chunks
