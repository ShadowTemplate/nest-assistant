# data/ — real Nest documents live here, and nowhere in git

Everything in this directory is **gitignored** (see `.gitignore` and
`docs/DATA_POLICY.md`). That is not a suggestion; there is a pre-commit hook and
a CI job that enforce it.

## What goes here

- The document dump from the Nest Drive folder
- `manifest.yaml` — TEAM 1's inventory (task W1-1.1)
- `INVENTORY.md` — what exists, what is missing, what is stale
- `allowlist.json` — Telegram id → tier, for TEAM 4. Contains real people's ids,
  so it is personal data and it stays here.

## How to get it

Ask Gianvito. You will get a link to the Drive folder; download it into this
directory. Do not forward the link, do not re-upload it anywhere, and do not
paste excerpts into a chat.

## Working without it

The pipeline reads from `fixtures/` when `data/` is empty. Every task on the
board can be done against the synthetic corpus. If you are waiting on real data,
you are not blocked — you are working against a schema you cannot see, which is
what regulated software work actually feels like.
