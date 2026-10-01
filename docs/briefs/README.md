# Team briefs — Workshop 1, October 2026

One page per team. **Print all six; hand each team its own at 10:15.**

They are in English because everything you will read all day — code, docstrings,
tests, `ARCHITECTURE.md` — is in English. The room is Italian; the repository is
not. Mixing the two inside a task is how a term drifts.

| | Team | Owns | Brief |
|---|---|---|---|
| 1 | **INGEST** | `ingest.build_chunks()` | [team-1-ingest.md](team-1-ingest.md) |
| 2 | **INDEX** | `index.search()` | [team-2-index.md](team-2-index.md) |
| 3 | **ANSWER** | `answer.generate()` | [team-3-answer.md](team-3-answer.md) |
| 4 | **CHAT** | `identity.resolve()`, `bot.run()` | [team-4-chat.md](team-4-chat.md) |
| 5 | **EVAL** | `evaluate.run()`, `guardrails.apply()` | [team-5-eval.md](team-5-eval.md) |
| 6 | **PLATFORM & PM** | the seams, and the humans | [team-6-platform-pm.md](team-6-platform-pm.md) |

## The shape of the day

| | |
|---|---|
| 10:30–12:30 | **Block A** — task 1 |
| 12:30–13:30 | Lunch. Not a work block. |
| 13:30–15:15 | **Block B** — task 2 |
| 15:15–15:30 | **Checkpoint** — 90 seconds per team, standing up |
| 15:30–16:30 | **Block C** — task 3, the droppable one |
| 16:15 | All-room red team, 15 minutes |
| 16:30 | **Freeze.** Merge, `make check`, `make eval`, scorecard on screen |
| 17:00 | Close |

## The one instruction for everybody

> **Everything already works. Right now, badly, with fake data — but it runs.
> Your job is to replace your piece with a real one without breaking anyone
> else's. Nobody in this room is blocked on anybody else. If you think you are,
> come and find me, because you're wrong and it's my fault.**

## The four rules

1. **Never commit a Nest document or a key.** The repository is public. See
   `docs/DATA_POLICY.md`. Hooks will stop you; be the first line of defence
   anyway.
2. **`make check` must be green before you push.** The pipeline is never broken.
3. **Your interface does not change** without the coordinators agreeing and
   telling everyone.
4. **Flip `STATUS = "real"` in your module only when it is.** `make board` reads
   it, and the board goes on the whiteboard.

## When you are stuck

Fifteen minutes on your own → your team → the team you think you are blocked on
→ **the PM coordinators** → Gianvito. Each brief names the one thing to take to
the coordinators rather than to Gianvito. The queue exists so that he is
interrupted once per team, not once per person.
