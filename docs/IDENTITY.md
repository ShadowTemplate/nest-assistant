# How do we know someone actually lives at Nest?

> **TEAM 4 owns this document — it is the real deliverable of task W1-4.2.**
> The code for that task is an allowlist and twenty lines. This is the part that
> takes thinking, and the part March 2027 will implement.
>
> What follows is a skeleton with the questions you have to answer, plus a
> starting sketch of the options. Rewrite it; do not just fill blanks.

## The problem

`identity.resolve(user_id) -> Tier` decides whether the assistant treats someone
as `public`, `resident` or `staff`. Everything downstream trusts that answer:
retrieval filters on it, and a wrong answer either leaks internal information to
a stranger or makes the assistant useless to the people who live here.

All we get from Telegram is a numeric user id and whatever display name the
person chose. Nothing in that is evidence of anything.

Note the two separate questions, which are easy to blur:

- **Authentication** — is this person who they claim to be?
- **Authorisation** — what is this person allowed to see?

We do authorisation well already (tiers, filtered retrieval). Authentication is
the open problem, and most of it happens at a reception desk rather than in
Python.

## What W1 actually ships

An allowlist in `data/allowlist.json`, maintained by hand:

```json
{
  "telegram:123456789": "resident",
  "telegram:987654321": "staff"
}
```

Unknown id → `public`. Fails open, on purpose: the cost of a stranger reading the
house rules is much lower than the cost of locking out a resident who needs an
answer at 23:00.

This does not scale past about twenty people and it is nobody's idea of a
solution. It buys us a working demo while we design the real thing.

## The options

<!-- TEAM 4: expand at least two of these properly, and add any you think of. -->

### A. One-time code from the secretariat

The secretariat gives each resident a code at check-in; the resident sends
`/verifica CODICE` to the bot once.

- Strong link to a real check-in that already happens
- Codes can be shared; needs an expiry and single use
- Needs the secretariat to do something — a process cost, every September

### B. Email domain check

Send a code to a `@unitn.it` address.

- Cheap, self-service, no staff involvement
- Proves *student*, not *resident of Nest* — which is the wrong question
- Non-UniTrento residents are excluded

### C. QR code on arrival

A QR poster at reception, or on the welcome pack, that opens the bot with a
signed token.

- Very low friction; works at the moment somebody is physically here
- A photo of the poster works from anywhere; needs rotation and an expiry

### D. Staff-approved join request

The resident asks; a staff member taps approve.

- Highest confidence; a human checks
- Someone has to be available. What happens on a Saturday night?

### E. Something else

<!-- Your idea here. There are good ones we have not thought of. -->

## The questions your note must answer

1. Which option, and why that one rather than the others?
2. What does the **secretariat** have to do, in what season, and how often? An
   option that needs staff work in September that nobody scheduled will not
   happen.
3. What happens when someone **leaves**? A resident who moved out keeps their
   Telegram account. Who revokes, and when? Is there an expiry?
4. What is the **failure mode**? If verification breaks at 23:00 on a Sunday,
   what does the resident experience?
5. What personal data does this create, where does it live, and how long do we
   keep it? (This feeds directly into W2's GDPR work.)
6. How would you **attack** it? Give it to team 5 and ask them to break it.

## Threat model

Who might try to get a tier they are not entitled to, and how hard would they
try?

| Who | Wants | Effort they would spend | Cost if they succeed |
|---|---|---|---|
| Curious resident | staff-tier information | low, opportunistic | low–medium |
| Prospective student | resident-tier information | low | low |
| Ex-resident | continued access | low | low |
| Someone with a grudge | anything embarrassing | medium | **high — reputational** |

Being honest about this matters: the realistic threat here is not a determined
attacker, it is a bored resident at midnight and an ex-resident nobody
deactivated. Design for those two and you have covered most of it.

## Recommendation

<!-- TEAM 4: one clear recommendation, in one paragraph, that March can build. -->
