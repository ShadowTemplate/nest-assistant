"""The data scanner has to actually work.

From the preparation plan: *"Try to commit a file containing an Italian address
and a plausible IBAN, and verify it is blocked. If it does not catch that, it
will not catch the real thing."*

So: that exact test, plus the false-positive cases that would otherwise make
people disable the hook — which is the real failure mode of any scanner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import scan_data  # noqa: E402


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- the test the preparation plan asks for ---------------------------------


def test_it_catches_an_italian_address_and_a_plausible_iban(tmp_path: Path):
    # The `nest-scan: allow` markers in this file are the escape hatch doing its
    # job: these are invented samples, and without the markers the scanner would
    # (correctly) block its own test suite.
    path = write(
        tmp_path,
        "residente.md",
        "Mario Rossi\nVia Giuseppe Verdi, 14\n"  # nest-scan: allow
        "38122 Trento\nIBAN IT60X0542811101000000123456\n",  # nest-scan: allow
    )
    findings = scan_data.scan([path])
    kinds = {f.kind for f in findings}
    assert "Italian address" in kinds
    assert "IBAN" in kinds


# --- everything else it must catch ------------------------------------------

# The marker has to sit on the same line as the sample, so the samples are
# named constants rather than inline literals. All of them are invented.
FAKE_KEY = 'ANTHROPIC_KEY = "sk-ant-api03-REDACTEDvalue12345"'  # nest-scan: allow
FAKE_TOKEN = "token 1234567890:AAHfSHFyeuiw-XCVBnmasdfghjkl1234567"  # nest-scan: allow


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        ("codice fiscale RSSMRA85M01H501Z", "codice fiscale"),  # nest-scan: allow
        ("chiamami al +39 340 1234567", "Italian phone number"),  # nest-scan: allow
        ("scrivi a mario.rossi@nest-trento.it", "email address"),  # nest-scan: allow
        (FAKE_KEY, "Anthropic API key"),
        (FAKE_TOKEN, "Telegram bot token"),
        ('password = "hunter2isnotgoodenough"', "generic secret assignment"),  # nest-scan: allow
    ],
)
def test_it_catches_the_usual_suspects(tmp_path: Path, content: str, kind: str):
    findings = scan_data.scan([write(tmp_path, "note.md", content)])
    assert kind in {f.kind for f in findings}, f"missed: {kind}"


def test_it_blocks_files_under_data_regardless_of_content():
    findings = scan_data.check_path(Path("data/regolamento.md"))
    assert findings and "forbidden location" in findings[0].kind


def test_it_allows_the_two_files_data_legitimately_commits():
    """``.gitignore`` un-ignores these two, so the scanner must agree with it."""
    assert not scan_data.check_path(Path("data/README.md"))
    assert not scan_data.check_path(Path("data/.gitkeep"))


def test_a_tree_scan_walks_past_the_real_corpus():
    """A laptop with the real Nest documents in ``data/`` still gets a clean scan.

    They are gitignored; they are supposed to be there. Blocking a *commit* of
    them is the job (see the test above), and pre-commit passes staged paths in
    explicitly.
    """
    root = Path(__file__).resolve().parents[1]
    walked = [p.relative_to(root) for p in scan_data.all_files(root)]
    assert not any(p.parts[0] == "data" for p in walked)


def test_it_blocks_document_formats_anywhere(tmp_path: Path):
    for name in ["prezzi.pdf", "elenco.xlsx", "regolamento.docx"]:
        assert scan_data.check_path(Path(name)), f"{name} should be blocked"


def test_findings_are_redacted_not_reprinted():
    """The scanner must not print the secret it just caught into a CI log."""
    sample = "IT60X0542811101000000123456"  # nest-scan: allow
    assert "0000001234" not in scan_data.redact(sample)


# --- and what it must NOT catch ---------------------------------------------
# A scanner that cries wolf gets switched off, and then it protects nothing.


@pytest.mark.parametrize(
    "content",
    [
        "ANTHROPIC_API_KEY=",
        "ANTHROPIC_API_KEY=your-key-here",
        "scrivi a nome.cognome@example.com",
        "vedi https://example.com/docs",
        "La tariffa mensile è di 480 euro.",
        "Il silenzio è dalle 23:00 alle 07:00.",
        "password = '<your password>'",
    ],
)
def test_it_does_not_cry_wolf(tmp_path: Path, content: str):
    assert not scan_data.scan([write(tmp_path, "ok.md", content)]), content


def test_the_allow_marker_works(tmp_path: Path):
    clean = "IBAN IT60X0542811101000000123456  # nest-scan: allow (synthetic example)"
    assert not scan_data.scan([write(tmp_path, "fixture.md", clean)])


def test_the_repository_itself_is_clean():
    """Meta-test: this repo must pass its own scanner."""
    root = Path(__file__).resolve().parents[1]
    findings = scan_data.scan(scan_data.all_files(root))
    assert not findings, "\n" + "\n".join(str(f) for f in findings)
