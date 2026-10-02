#!/usr/bin/env python3
"""Block Nest data and secrets from entering a public repository.

TEAM 6 owns this (task W1-6.1). It runs as a pre-commit hook and in CI.

The rule it enforces is the one rule of this repository that has no exceptions:
**no Nest document, and no secret, is ever committed.** The repository is public.
Students list it on their CVs. A leaked resident's address does not get un-leaked
by a follow-up commit.

Two checks:

1. **Path rules.** Files under ``data/`` and document formats (pdf, docx, xlsx…)
   have no business in git at all, whatever is inside them.
2. **Content rules.** Text that looks like an IBAN, an Italian codice fiscale, a
   street address, a phone number, an email, or an API key.

Both are noisy on purpose. A false positive costs someone thirty seconds and an
``--allow`` marker. A false negative costs Nest a data breach.

Usage::

    python tools/scan_data.py FILE [FILE ...]     # scan specific files
    python tools/scan_data.py --staged            # scan what git is about to commit
    python tools/scan_data.py --all               # scan the whole tree

Exit code 0 = clean, 1 = something was found.

Escape hatch: put ``nest-scan: allow`` in a comment on the same line. Use it for
the synthetic fixtures and for regex patterns in this file — and never because a
finding is inconvenient. If you find yourself allowlisting a real document, stop
and go and talk to Gianvito.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ALLOW_MARKER = "nest-scan: allow"

# Paths that must never be committed, regardless of content.
FORBIDDEN_DIRS = {"data"}

# ...with exactly two exceptions, which `.gitignore` also un-ignores.
ALLOWED_IN_DATA = {"README.md", ".gitkeep"}
FORBIDDEN_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".tsv",
    ".odt",
    ".ods",
    ".eml",
    ".msg",
    ".zip",
}

# Directories we never even look at.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "build",
    ".ruff_cache",
    ".pytest_cache",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".sh",
    ".html",
    ".css",
    ".js",
    ".ts",
    "",
}

PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "IBAN",
        re.compile(r"\b[A-Z]{2}\d{2}[ ]?[A-Z0-9]{4}[ ]?(?:[0-9A-Z]{4}[ ]?){2,7}[0-9A-Z]{1,4}\b"),
        "a bank account number",
    ),
    (
        "codice fiscale",
        re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPRST]\d{2}[A-Z]\d{3}[A-Z]\b"),
        "an Italian tax code — personal data",
    ),
    (
        "Italian address",
        re.compile(
            r"\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada)\s+[A-ZÀ-Ù][\w'À-ù.]*"
            r"(?:\s+[\w'À-ù.]+){0,4},?\s*\d{1,4}\b",
            re.IGNORECASE,
        ),
        "a street address",
    ),
    (
        "Italian phone number",
        re.compile(r"(?:\+39[ .-]?)?\b3\d{2}[ .-]?\d{3}[ .-]?\d{4}\b"),
        "a mobile phone number",
    ),
    (
        "email address",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
        "an email address",
    ),
    (
        "Anthropic API key",
        re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
        "an API key",
    ),
    (
        "Telegram bot token",
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
        "a bot token — this is a password",
    ),
    (
        "generic secret assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*['\"][^'\"\s]{12,}['\"]"
        ),
        "a hardcoded credential",
    ),
]

# Placeholders that look like findings but are not.
SAFE_VALUES = re.compile(
    r"(?i)(example\.com|localhost|your[-_]?key|xxx+|<[^>]+>|changeme|placeholder|"
    r"sk-ant-api03-\.\.\.|nome\.cognome|noreply@)"
)


class Finding:
    __slots__ = ("path", "line_no", "kind", "why", "excerpt")

    def __init__(self, path: Path, line_no: int, kind: str, why: str, excerpt: str) -> None:
        self.path = path
        self.line_no = line_no
        self.kind = kind
        self.why = why
        self.excerpt = excerpt

    def __str__(self) -> str:
        location = f"{self.path}:{self.line_no}" if self.line_no else str(self.path)
        return f"  {location}\n      {self.kind}: {self.why}\n      > {self.excerpt}"


def redact(text: str) -> str:
    """Show enough of a match to find it, not enough to leak it."""
    text = text.strip()
    if len(text) <= 24:
        return text[:6] + "…" if len(text) > 8 else text
    return text[:12] + "…" + text[-4:]


def check_path(path: Path) -> list[Finding]:
    parts = set(path.parts)
    if parts & FORBIDDEN_DIRS and path.name not in ALLOWED_IN_DATA:
        return [
            Finding(
                path,
                0,
                "forbidden location",
                "files under data/ are Nest documents and are never committed",
                str(path),
            )
        ]
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return [
            Finding(
                path,
                0,
                "forbidden file type",
                f"'{path.suffix}' is a document format — the corpus lives outside git",
                str(path),
            )
        ]
    return []


def check_content(path: Path) -> list[Finding]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for kind, pattern, why in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if SAFE_VALUES.search(value):
                    continue
                findings.append(Finding(path, line_no, kind, why, redact(value)))
                break
    return findings


def scan(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        findings.extend(check_path(path))
        findings.extend(check_content(path))
    return findings


def staged_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [Path(line) for line in out.stdout.splitlines() if line]


def all_files(root: Path) -> list[Path]:
    """Every file worth scanning in the tree: everything git could commit.

    Gitignored files are walked past, not into — ``data/`` with the real corpus,
    ``.env`` with your team's key, ``build/`` with generated chunks. They are not
    a leak; they are exactly where they belong, and scanning them would turn
    ``make check`` red on every laptop that followed the setup instructions. A
    gitignored file that is *force-staged* still gets blocked: pre-commit passes
    staged paths in explicitly, and :func:`check_path` catches them there.

    Outside a git checkout (a downloaded zip), falls back to walking the tree.
    """
    skip = SKIP_DIRS | FORBIDDEN_DIRS
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        candidates = [root / name for name in out.stdout.split("\0") if name]
    except (subprocess.CalledProcessError, FileNotFoundError):
        candidates = list(root.rglob("*"))
    return [p for p in candidates if p.is_file() and not (set(p.parts) & skip)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block Nest data and secrets from git.")
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--staged", action="store_true", help="scan files staged for commit")
    parser.add_argument("--all", action="store_true", help="scan the whole working tree")
    args = parser.parse_args(argv)

    if args.staged:
        paths = staged_files()
    elif args.all:
        paths = all_files(Path.cwd())
    else:
        paths = args.files

    if not paths:
        return 0

    findings = scan(paths)
    if not findings:
        return 0

    print("\n\033[31mBLOCKED — this looks like Nest data or a secret.\033[0m\n")
    for finding in findings:
        print(finding)
    print(
        "\nThe repository is public. Nothing above goes into it.\n"
        "  • A real document?  Move it to data/ (gitignored) or Google Drive.\n"
        "  • A real secret?    Put it in .env, and rotate it — it may already be in your history.\n"
        f"  • A false positive? Add a comment '{ALLOW_MARKER}' on that line, and say why.\n"
        "\nSee docs/DATA_POLICY.md.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
