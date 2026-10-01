# Data policy

**This repository is public.** Anyone can read it. Students list it on their CVs,
which is part of the point — and it means everything in it is permanent.

## The rule

**No Nest document and no secret ever enters this repository.**

There is no exception for "just for testing", "only a screenshot", "it's not
sensitive", or "I'll remove it in the next commit". Git does not forget: a
document committed and then deleted is still in the history, still on GitHub,
still in every clone anyone made in between.

## What counts as a Nest document

Anything that came from Nest and was not written by us for this repository:

- price lists, contracts, house rules, admission criteria — even the public ones
- anything with a resident's, applicant's or staff member's name in it
- addresses, phone numbers, email addresses, IBANs, codici fiscali
- spreadsheets, PDFs, Word files, scans, exports — any format at all
- screenshots of any of the above
- the Telegram id → tier allowlist, because it maps real people to accounts

When in doubt: it goes in `data/`.

## What counts as a secret

- `ANTHROPIC_API_KEY` — spends your team's money, and then somebody else's
- `TELEGRAM_BOT_TOKEN` — lets a stranger run a bot that speaks as Nest
- anything from the Nest server, later in the project

Secrets go in `.env`. `.env` is gitignored. `.env.example` shows the shape with
empty values, and that is the only one that gets committed.

## Where things actually live

| What | Where | In git? |
|---|---|---|
| Real Nest documents | `data/`, or the Drive folder | **No** |
| The manifest and inventory of them | `data/manifest.yaml`, `data/INVENTORY.md` | **No** |
| Generated chunks | `build/chunks.jsonl` | **No** |
| Telegram allowlist | `data/allowlist.json` | **No** |
| Keys and tokens | `.env` | **No** |
| Synthetic Nest-*like* documents | `fixtures/` | Yes — they are invented |
| Eval questions and scorecards | `eval/` | Yes — questions and numbers, not documents |
| Code, prompts, docs | everywhere else | Yes |

Note that `eval/questions.yaml` is committed. Questions are fine; *answers copied
out of a Nest document* are not. Write the expected answer as the key fact
("480", "due mensilità"), never as a quoted paragraph.

## What enforces this

Three layers, in the order they catch things:

1. **`.gitignore`** — `data/`, `.env`, and every document extension. Git will not
   even offer to add them.
2. **`tools/scan_data.py`** — runs as a pre-commit hook and in CI. Looks for
   IBANs, codici fiscali, addresses, phone numbers, emails, and API keys, and
   refuses the commit. Install it with `make hooks`; check the whole tree any
   time with `make scan`.
3. **`gitleaks`** — a second, independent secret scanner, because a scanner we
   wrote ourselves this morning should not be the only one.

The scanner is noisy on purpose. A false positive costs you thirty seconds and a
`# nest-scan: allow` comment. A false negative costs Nest a data breach.

## If it happens anyway

It might. Say so **immediately** — in the Telegram group, out loud in the room,
whatever is fastest. Then:

1. **Stop.** Do not push anything else, and do not try to fix it with a normal
   commit — that adds a second copy rather than removing the first.
2. **Rotate anything exposed.** A leaked key is leaked from the moment it is
   pushed; deleting it later does not un-leak it. New key, immediately.
3. **Get help before rewriting history.** Removing a file from git history is
   possible and fiddly, and doing it wrong under stress makes it worse.
4. **Write down what happened**, in the checkpoint document. Not to assign blame
   — to make the next person's mistake less likely.

Nobody is in trouble for reporting this fast. The only expensive mistake is the
quiet one.
