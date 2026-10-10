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


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------
def test_split_long_keeps_the_space_between_sentences():
    unit = " ".join(f"Questa è la frase numero {i} del regolamento." for i in range(60))
    assert len(unit) > ingest.MAX_CHARS
    pieces = ingest._split_long(unit)
    assert len(pieces) > 1
    assert all(len(p) <= ingest.MAX_CHARS for p in pieces)
    # nothing lost, nothing glued: ".Questa" is the bug this guards against
    assert " ".join(pieces) == unit
    assert not any(".Questa" in p for p in pieces)


def test_split_long_leaves_short_units_alone():
    assert ingest._split_long("Breve.") == ["Breve."]


def test_pack_merges_small_units_and_respects_the_target():
    small = ["a" * 300] * 4
    packed = ingest._pack(small)
    assert all(len(p) <= ingest.TARGET_CHARS for p in packed)
    assert len(packed) < len(small)
    assert "".join(packed).replace("\n", "") == "".join(small)


def test_pack_never_drops_an_oversized_unit():
    big = " ".join(f"Frase {i}." for i in range(400))
    assert " ".join(ingest._pack([big])).replace("\n", " ") == big


def test_join_reflows_wrapped_prose_and_keeps_table_rows():
    wrapped = ["x" * 70, "continua qui."]
    assert ingest._join(wrapped) == "x" * 70 + " continua qui."
    assert ingest._join(["Singola", "10.450"]) == "Singola\n10.450"
    assert ingest._join(["il magi-", "strale"]) == "il magistrale"


def test_question_detection_needs_caps_and_a_question_mark():
    assert ingest._is_question("COME FUNZIONA LA LAVANDERIA?")
    assert not ingest._is_question("Come funziona la lavanderia?")
    assert not ingest._is_question("COME FUNZIONA LA LAVANDERIA")


def test_each_question_starts_its_own_unit():
    sections = ingest._sections(
        ["A LAVANDERIA APRE?", "Tutti i giorni.", "B COME SI PAGA?", "Al banco."]
    )
    assert [u for s in sections for u in s.units] == [
        "A LAVANDERIA APRE?\nTutti i giorni.",
        "B COME SI PAGA?\nAl banco.",
    ]


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
def test_furniture_repeated_on_half_the_pages_is_removed():
    pages = [(f"NEST COLLEGE\nCorpo della pagina {i}.\n{i}", "") for i in range(1, 5)]
    cleaned = ingest._clean_pages(pages, "x.pdf", pdf=True)
    flat = [ln for page in cleaned for ln in page]
    assert "NEST COLLEGE" not in flat
    assert not any(ln.isdigit() for ln in flat)
    assert "Corpo della pagina 2." in flat


def test_page_numbers_survive_outside_pdfs():
    cleaned = ingest._clean_pages([("Camere\n12\n1/2", "")], "note.md")
    assert cleaned == [["Camere", "12", "1/2"]]


def test_back_to_index_links_are_removed():
    assert ingest._clean_pages([("Testo\nTorna all'indice", "")]) == [["Testo"]]


def test_price_table_page_is_not_mistaken_for_labels():
    table = ["Singola", "€ 450", "Doppia", "€ 320", "Studio", "€ 610"]
    assert not ingest._is_label_page(table)
    assert not ingest._is_label_page(["Palestra", "7:00", "Sala", "9:00", "Bar", "8.30"])
    assert ingest._is_label_page(["HOUSE", "LAB", "BAR", "HALL"])


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "manifest",
    [
        "documents:\n",  # None
        "",  # empty file
        "documents:\n  - just-a-string\n",
        "documents:\n  - {filename: a.md, lang: it, tier: secret}\n",
        "documents:\n  - {filename: a.md, lang: it, tier: public}\n"
        "  - {filename: a.md, lang: it, tier: public}\n",
    ],
)
def test_bad_manifest_raises_a_clear_valueerror(tmp_path: Path, manifest: str):
    (tmp_path / "manifest.yaml").write_text(manifest, encoding="utf-8")
    with pytest.raises(ValueError):
        ingest.build_chunks(tmp_path)


def test_txt_comment_lines_are_dropped_but_md_headings_are_not(tmp_path: Path):
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n  - {filename: n.txt, lang: it, tier: staff}\n"
        "  - {filename: n.md, lang: it, tier: staff}\n",
        encoding="utf-8",
    )
    (tmp_path / "n.txt").write_text("# nota del curatore\nStanza 101\n", encoding="utf-8")
    (tmp_path / "n.md").write_text("# Titolo\nStanza 101\n", encoding="utf-8")
    by_source = {c.source: c for c in ingest.build_chunks(tmp_path)}
    assert "nota del curatore" not in by_source["n.txt"].text
    assert by_source["n.md"].section == "Titolo"


# ---------------------------------------------------------------------------
# A synthetic PDF through the whole pipeline
# ---------------------------------------------------------------------------
def _pdf(pages: list[list[str]]) -> bytes:
    """A minimal text PDF, one list of lines per page. No dependency beyond pypdf."""
    objs: list[bytes] = []
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        body = "BT /F1 11 Tf 14 TL 50 780 Td " + " T* ".join(f"({ln}) Tj" for ln in lines) + " ET"
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream".encode())
    out = b"%PDF-1.4\n"
    offsets = []
    for n, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_pdf_path_end_to_end(tmp_path: Path):
    pytest.importorskip("pypdf", reason="needs the ingest extra: uv sync --extra ingest")

    def prose(n: int) -> list[str]:  # distinct per page, or it would count as furniture
        return [
            f"La retta della camera singola e di 10.450 euro all anno, rata numero {n}.",
            f"Il pagamento va effettuato entro il giorno {n} del mese, senza eccezioni.",
        ]

    pages = [
        ["NEST COLLEGE", "1. AMMISSIONI", *prose(1), "2"],
        ["NEST COLLEGE", "2. RETTE", *prose(2), "3"],
        ["NEST COLLEGE", "3. OSPITI", *prose(3), "4"],
        ["NEST COLLEGE", "HOUSE", "LAB", "BAR", "5"],  # a labels-only page
    ]
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n  - {filename: bando.pdf, lang: it, tier: public}\n", encoding="utf-8"
    )
    (tmp_path / "bando.pdf").write_bytes(_pdf(pages))

    chunks = ingest.build_chunks(tmp_path)

    assert {c.tier for c in chunks} == {"public"}
    assert {c.source for c in chunks} == {"bando.pdf"}
    assert {"1. AMMISSIONI", "2. RETTE", "3. OSPITI"} <= {c.section for c in chunks}
    text = "\n".join(c.text for c in chunks)
    assert "NEST COLLEGE" not in text  # running header
    assert "HOUSE" not in text  # label page dropped
    assert "10.450" in text
    assert [c.id for c in chunks] == [f"bando.pdf#{i}" for i in range(1, len(chunks) + 1)]


# ---------------------------------------------------------------------------
# Review round 2
# ---------------------------------------------------------------------------
def test_values_in_a_pdf_table_are_not_taken_for_page_numbers():
    page = "Retta\nSingola\n450\nDoppia\n320\nStudio\n610"
    cleaned = ingest._clean_pages([(page, "")], "listino.pdf", pdf=True)
    assert cleaned == [["Retta", "Singola", "450", "Doppia", "320", "Studio", "610"]]


def test_page_number_at_the_edge_of_a_pdf_page_is_removed():
    pages = [("Testo uno\n1", ""), ("2\nTesto due", ""), ("Testo tre\npag. 3 di 9", "")]
    cleaned = ingest._clean_pages(pages, "x.pdf", pdf=True)
    assert cleaned == [["Testo uno"], ["Testo due"], ["Testo tre"]]


def test_a_short_page_of_sentences_is_not_a_label_page():
    assert not ingest._is_label_page(
        ["Il silenzio è richiesto di notte.", "Gli ospiti vanno annunciati."]
    )
    assert ingest._is_label_page(["NEST", "2026-2027"])


@pytest.mark.parametrize(
    "unit",
    [
        "x" * 3000,  # no separator at all
        "\n".join(["riga " + "y" * 60] * 40),  # lines
        "parola " * 400,  # one sentence longer than MAX_CHARS
        " ".join(["Frase di prova numero uno."] * 80),
    ],
    ids=["no-separator", "lines", "long-sentence", "sentences"],
)
@pytest.mark.parametrize("reserve", [0, 120])
def test_no_piece_is_longer_than_the_limit(unit: str, reserve: int):
    pieces = ingest._split_long(unit, reserve)
    assert pieces
    assert all(len(p) <= ingest.MAX_CHARS - reserve for p in pieces)
    assert "".join(pieces).replace(" ", "").replace("\n", "") == unit.replace(" ", "").replace(
        "\n", ""
    )


def test_split_long_does_not_cut_after_an_abbreviation():
    # Sized so the chunk would fill up exactly at "Art.": the cut lands there
    # unless the abbreviation is recognised.
    unit = (
        ("Frase uno è lunga abbastanza. " * 28)
        + "Vedi Art. 5 del bando e delle sue successive modifiche e integrazioni. "
        + ("Altro testo. " * 40)
    )
    assert len(unit) > ingest.MAX_CHARS
    pieces = ingest._split_long(unit)
    assert len(pieces) > 1
    assert not any(p.endswith("Art.") for p in pieces)
    assert any("Art. 5 del bando" in p for p in pieces)


def test_list_items_are_not_sections_but_real_subclauses_are():
    lines = [
        "1. REQUISITI",
        "Per partecipare serve quanto segue, come indicato nel bando di quest anno.",
        "a. Essere maggiorenni",
        "b. Essere iscritti",
        "c. Avere un ISEE valido",
        "2. OFFERTA",
        "a. Programma offerto",
        "Il programma comprende laboratori, seminari e attività di gruppo ogni settimana.",
    ]
    titles = [s.title for s in ingest._sections(lines)]
    assert titles == ["1. REQUISITI", "2. OFFERTA > a. Programma offerto"]


def test_join_keeps_the_hyphen_in_compounds():
    assert ingest._join(["x" * 60 + " il check-", "in avviene alle 15"]).endswith(
        "check-in avviene alle 15"
    )
    assert ingest._join(["il magi-", "strale"]) == "il magistrale"


def test_chunk_size_counts_the_section_title(tmp_path: Path):
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n  - {filename: a.md, lang: it, tier: public}\n", encoding="utf-8"
    )
    title = "T" * 80
    body = "\n".join(f"- voce numero {i} del regolamento interno, da leggere" for i in range(60))
    (tmp_path / "a.md").write_text(f"# {title}\n{body}\n", encoding="utf-8")
    chunks = ingest.build_chunks(tmp_path)
    assert len(chunks) > 1
    assert all(len(c.text) <= ingest.TARGET_CHARS for c in chunks)


def test_ids_of_one_document_do_not_depend_on_another(corpus: Path):
    before = {c.id for c in ingest.build_chunks(corpus) if c.source == "interno.txt"}
    (corpus / "aperto.md").write_text("# Nuovo\n\nTutto cambiato.\n", encoding="utf-8")
    after = {c.id for c in ingest.build_chunks(corpus) if c.source == "interno.txt"}
    assert before == after


def test_duplicate_lines_keep_their_place_in_layout_order():
    layout = (
        "Intestazione lunga\n   Prezzo base annuo\n   Voce ripetuta qui\n"
        "   Altro testo lungo\n   Voce ripetuta qui\n"
    )
    page = ["Intestazione lunga", "Voce ripetuta qui", "Altro testo lungo", "Voce ripetuta qui"]
    assert ingest._in_layout_order(page, layout) == page


def test_docx_tables_are_read_in_order(tmp_path: Path):
    docx = pytest.importorskip("docx", reason="needs the ingest extra: uv sync --extra ingest")
    doc = docx.Document()
    doc.add_paragraph("Listino")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Singola", "450"
    table.cell(1, 0).text, table.cell(1, 1).text = "Doppia", "320"
    doc.add_paragraph("Fine")
    doc.save(tmp_path / "listino.docx")
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n  - {filename: listino.docx, lang: it, tier: public}\n", encoding="utf-8"
    )
    text = ingest.build_chunks(tmp_path)[0].text
    assert text.index("Listino") < text.index("Singola | 450") < text.index("Doppia | 320")
    assert text.index("Doppia | 320") < text.index("Fine")
