"""INGEST contract: tiers come from the manifest, ids are stable, text is clean.

Runs on a throwaway synthetic corpus, never on data/.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from nest_assistant import ingest
from nest_assistant.schema import TIERS

MANIFEST = """\
documents:
  - {filename: aperto.md, lang: it, tier: public}
  - {filename: interno.txt, lang: en, tier: staff}
"""


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    (tmp_path / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    (tmp_path / "aperto.md").write_text(
        "# Rette\n\nLa singola costa 10.450 euro.\x0c\n\n# Ospiti\n\nOrario 9-21.\n",
        encoding="utf-8",
    )
    (tmp_path / "interno.txt").write_text("Solo per la segreteria.\n", encoding="utf-8")
    return tmp_path


def test_tier_and_lang_come_from_the_manifest(corpus: Path):
    by_source = {c.source: c for c in ingest.build_chunks(corpus)}
    assert by_source["aperto.md"].tier == "public"
    assert by_source["interno.txt"].tier == "staff"
    assert by_source["interno.txt"].lang == "en"
    assert all(c.tier in TIERS for c in by_source.values())


def test_document_without_manifest_entry_is_not_ingested(corpus: Path, caplog):
    (corpus / "segreto.txt").write_text("IBAN e password.", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        chunks = ingest.build_chunks(corpus)
    assert "segreto.txt" not in {c.source for c in chunks}
    assert "segreto.txt" in caplog.text  # and it is reported


def test_no_manifest_means_nothing_is_ingested(tmp_path: Path):
    (tmp_path / "a.md").write_text("ciao", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        ingest.build_chunks(tmp_path)


def test_ids_are_stable_and_unique(corpus: Path):
    first = [c.id for c in ingest.build_chunks(corpus)]
    assert first == [c.id for c in ingest.build_chunks(corpus)]
    assert len(first) == len(set(first))


def test_text_is_clean(corpus: Path):
    for chunk in ingest.build_chunks(corpus):
        assert "\x0c" not in chunk.text
        assert chunk.text == chunk.text.strip()


def test_sections_split_on_headings(corpus: Path):
    sections = {c.section for c in ingest.build_chunks(corpus) if c.source == "aperto.md"}
    assert {"Rette", "Ospiti"} <= sections
