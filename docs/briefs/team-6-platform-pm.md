# TEAM 6 — PLATFORM & PM
### *the seams, and the humans*

Two or three of you coordinate; the rest do cross-cutting engineering. Your work
is what makes the other five teams' work survive until March.

**You own** `.pre-commit-config.yaml`, `tools/scan_data.py`,
`.github/workflows/ci.yml`, `docs/PROGRESS.md`, and — by 17:00 —
`CHECKPOINT-2026-10.md`.

| | Task | Block | |
|---|---|---|---|
| A | W1-6.1 Data hygiene enforcement | 120 min | |
| B | W1-6.2 Integration and CI | 105 min | |
| C | W1-6.3 Coordination and the checkpoint | **all day**, then 60 min | |

---

## A · Data hygiene enforcement

**Produce** pre-commit hooks and the data scanner **actually installed on all
thirty laptops** — `make hooks`, walked round the room. Evidence: a deliberately
attempted bad commit, blocked, and the attempt documented.

**Done when** every laptop in the room has hooks installed and you have
demonstrated a blocked commit **to the room**.

The scanner exists and works; your job is that it is *running everywhere* and
that it catches what Nest's real documents actually look like. Test it against a
plausible fake — an Italian address, an IBAN, a codice fiscale. Tune the patterns
if the real corpus has a shape we did not anticipate.

> **Stuck 15 min?** `uv run pytest tests/test_data_scanner.py` shows the scanner's
> current behaviour in both directions — what it catches and what it must *not*
> flag. A scanner that cries wolf gets switched off, and then it protects
> nothing.

## B · Integration and CI

**Produce** `make check` green on every laptop; CI running on pull requests; and
the visible board of which stubs have been replaced.

**Done when** a pull request that breaks the pipeline fails before anyone merges
it, and the board on the whiteboard matches `make board`.

`make board` reads `STATUS` from each module, so it cannot lie. Update the
whiteboard from it at **12:25** and **15:15**, in front of everyone.

## C · Coordination — this is a real job, all day

**Throughout the day:**

- **Hold the question queue.** Gianvito gets interrupted once per team, not once
  per person. Filter, batch, and answer what you can yourselves.
- **Keep the progress board** (`docs/PROGRESS.md` and the whiteboard).
- **Own the tier register.** When team 1 asks "is this document resident or
  staff?", you are the single answer, so that six teams do not invent six.
- **Run the 15:15 checkpoint.** Six teams, 90 seconds each, standing up: what
  works that didn't at 10:30, what is blocked, what you need from another team.
  Enforce the clock — Gianvito says nothing for the first ten minutes.
- **Watch for the drowning team.** At 14:00, if one team is sinking and two are
  ahead, say so. Moving people onto the critical path is what happens on real
  projects.

**By 17:00: `CHECKPOINT-2026-10.md`.** Start it at **15:30**; do not let it slip
to 16:45.

It covers: what works, what is broken, what each team learned, what is next, who
knows what, and how to run it. **Write it for someone who has been away for four
months, because in March everyone will have been.**

**Done when** it is committed and pushed, and a person who was not here could
clone the repo and get the demo running from it alone.

> This document is the highest-leverage artefact of the whole four-workshop arc.
> Without it, March loses an hour to archaeology. Protect the thirty minutes it
> needs.

---

## What to escalate to Gianvito

An interface change; a decision about Nest as an organisation (staff time,
process, what may be shared); a team that is genuinely stuck rather than merely
loud; and **anybody committing a real Nest document** — that one stops the room,
immediately, and it is a ten-minute lesson worth having.

Everything else is yours.
