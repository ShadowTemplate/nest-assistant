# Nest Assistant

An AI assistant for **Nest**, a university residence in Trento, built by the
students who live there.

It answers questions from residents, their parents and Nest staff — over
Telegram, in Italian — **using only Nest's own documents**. When the documents do
not contain the answer, it says so instead of inventing one. That last sentence
is most of the engineering.

> **Status: workshop 1, October 2026.** Everything runs; most of it is
> deliberately fake. Run `make board` to see what is real yet.

---

## Quick start

```bash
git clone https://github.com/<nest-org>/nest-assistant.git
cd nest-assistant

make setup      # installs everything. Big download — do this on good wifi.
make check      # must print ✅ and a code
make demo       # asks the assistant three questions and prints the answers
```

`make demo` gives you obviously fake answers. **That is correct.** It works with
no API key, no internet and no Nest documents, because every component is a stub
until somebody replaces it. Replacing them is what the workshop is.

<details>
<summary>No <code>make</code> on your machine? (some Windows setups)</summary>

Every target is a one-line wrapper. Use these directly:

```bash
uv sync --all-extras     # = make setup
uv run nest check        # = make check
uv run pytest            # (make check runs this too)
uv run nest demo         # = make demo
uv run nest board        # = make board
uv run nest eval         # = make eval
uv run nest bot          # = make bot
```
</details>

## The two rules

1. **Never commit a Nest document.** Not a PDF, not a spreadsheet, not "just for
   testing". This repository is public. Real documents live in `data/`, which is
   gitignored, or in Drive. See [`docs/DATA_POLICY.md`](docs/DATA_POLICY.md).
2. **Never commit a key or a token.** Same reason. They go in `.env`, which is
   also gitignored. Start with `cp .env.example .env`.

There are pre-commit hooks that enforce both (`make hooks`), but they are the
second line of defence. You are the first.

## What is in here

```
src/nest_assistant/
├── schema.py      the contracts — Chunk, Answer, Tier. Read this first.
├── pipeline.py    the whole assistant, in thirty lines
├── ingest/        TEAM 1  documents in, clean chunks out
├── index/         TEAM 2  find the relevant text, for this person
├── answer/        TEAM 3  write the answer in Italian, or refuse
├── identity/      TEAM 4  who is asking
├── bot/           TEAM 4  Telegram
├── evaluate/      TEAM 5  is any of this working
├── guardrails.py  TEAM 5  last check before a human reads it
└── llm.py         the one place we talk to a model

fixtures/    synthetic Nest-like documents, in Italian. Committed. Invented.
data/        real Nest documents. Gitignored. Never committed.
eval/        the question set and the scorecards
prompts/     system prompts — reviewed and versioned, like any other logic
docs/        architecture, contributing, data policy
tools/       the data scanner that stops all of the above going wrong
```

## Commands

| Command | What it does |
|---|---|
| `make check` | Verify your environment and run the tests. **Must be green.** |
| `make demo` | Ask the assistant a question, end to end |
| `make board` | Which components are still stubs |
| `make ingest` | Build `chunks.jsonl` from the corpus |
| `make search Q="quanto costa una singola"` | Query the index directly |
| `make eval` | Score the system and print the card |
| `make bot` | Start the bot |
| `make scan` | Check the tree for Nest data and secrets |
| `make format` / `make lint` | Fix / check formatting |
| `make hooks` | Install the git pre-commit hooks |

## Documentation

| File | For |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **Everyone.** How the pieces fit together |
| [`docs/briefs/`](docs/briefs/) | **Your team.** Your three tasks, your interface, what "done" means |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | How we branch, commit and review |
| [`docs/DATA_POLICY.md`](docs/DATA_POLICY.md) | What may never enter this repository |
| [`docs/IDENTITY.md`](docs/IDENTITY.md) | Team 4's design note on verifying residents |
| [`eval/README.md`](eval/README.md) | What we measure, and what our numbers do not tell you |

## Where the data lives

The synthetic corpus in `fixtures/` is entirely invented — fake prices, fake
rules, fake activities, written in Italian with tier labels. It is what makes
this repository safe to be public, and it is enough to do every task in the
workshop.

The real Nest corpus goes in `data/`, which git will not accept. If `data/` has
content the pipeline uses it; otherwise it falls back to `fixtures/`. Nothing you
write should care which one it got.

## Licence

MIT for the code. The synthetic fixtures are invented and free to reuse. There is
no Nest data in this repository, and there never will be.
