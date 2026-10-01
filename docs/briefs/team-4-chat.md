# TEAM 4 — CHAT
### *the part everyone can see*

**You own** two files:

```python
# src/nest_assistant/bot/__init__.py
run() -> None
handle_message(text: str, user_id: str) -> str

# src/nest_assistant/identity/__init__.py
resolve(user_id: str) -> Tier
```

**You consume** nothing that can block you — the stub pipeline answers from
minute zero.
**You feed** the demo at 16:40, and the only impression anyone outside this room
will ever have of the project.

| | Task | Block | |
|---|---|---|---|
| A | W1-4.1 Telegram bot | 150 min | |
| B | W1-4.2 Identity and tier resolution | 105 min | |
| C | W1-4.3 Conversation context | 60 min | **droppable** |

---

## A · Telegram bot — get the visible win early, on purpose

**Produce** `bot/` running in polling mode via `make bot`; `/start`, `/help`,
`/reset`; the token loaded from the environment and demonstrably absent from git.

**Done when** somebody who is not on your team can message the bot from their
phone and get a reply. **When that happens, tell the room.** A working bot at
11:30 is worth a great deal of energy, and nobody else can see an embedding.

Two rules:

- **The token comes from `.env`.** Not from your code, not "just for a second".
  Prove it: `git grep` your token and find nothing.
- **Every reply goes through `handle_message()`**, so the console version and the
  Telegram version cannot drift apart. Telegram today; a phone line in 2028.

> **Stuck 15 min?** `make bot` already runs the console version against the real
> pipeline. If that answers and Telegram does not, your problem is Telegram, not
> the assistant — which is a much smaller problem.

## B · Identity and tier resolution

**Produce** `resolve()` backed by a simple allowlist in `data/allowlist.json`
(gitignored — it maps real people to real accounts) — **and, the real
deliverable, the design note in `docs/IDENTITY.md`**: how should verifying a
resident actually work? At least two options with their trade-offs. A one-time
code from the secretariat, an email domain check, a QR code on arrival, a
staff-approved join request — the skeleton of that document is already written,
with the questions you have to answer.

**Done when** the bot answers differently for a `public` and a `resident` user,
and the design note is in the repo for March to implement.

**Default to `public` on anything unexpected.** Unknown id, missing file, corrupt
file: `public`. Failing open means a stranger reads the house rules; failing
closed means a resident is locked out at 23:00. Only one of those is a real
problem. And `resolve()` never raises — it runs on every message.

> **Stuck 15 min?** The hard part of this task is a process at a reception desk,
> not Python. If you are stuck on code you are probably stuck on the wrong half —
> go and write the design note, then come back.

## C · Conversation context *(droppable)*

*"Quanto costa una singola?"* → *"E la doppia?"*

**Done when** the second question works — and you can explain why it is
meaningless to a retriever without the first.

---

## Not yours to change

`Tier`, and the `user_id` namespacing (`"telegram:123456"`), which is what stops
the 2028 phone line colliding with Telegram ids.

## Ask the coordinators, not Gianvito

**"Who goes on the allowlist for the demo?"** — and anything that would require
Nest to change a process. Both are decisions about other people's time, and the
coordinators are holding that conversation.
