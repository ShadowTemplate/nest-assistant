# Contributing

Six teams, one repository, one day. These rules exist so that thirty people can
push to the same place without the pipeline ever being broken.

## The one thing to internalise

**The pipeline must never be broken.** At any minute of the day, anybody must be
able to run `make check` and see it pass. That is what lets six teams work in
parallel without an integration disaster at 17:00.

So: commit small, commit often, and never push something you have not run
`make check` against.

## Branches

```bash
git switch -c team2/vector-index      # team<N>/<what-you-are-doing>
```

- Branch from `main`. Short names, in English.
- One branch per task, not one branch per team per day.
- `main` is protected: changes arrive by pull request.

## Commits

```
index: filter search results by tier

A public query can no longer surface a resident or staff chunk. Filtering
happens before ranking, so an excluded chunk cannot displace an included one.

Closes W1-2.2.
```

- English, present tense, prefix with your component.
- One logical change per commit.
- Say **why**, not just what. In March, `git log` is the only person left who
  remembers.

## Pull requests

Small PRs get reviewed in five minutes; big ones get reviewed at 16:50 by
somebody who has stopped reading carefully.

A PR needs:

- **What changed, and why.** Two sentences is often enough.
- **`make check` green**, and CI green.
- **One review** from outside your team. Yes, really — reading somebody else's
  component is how you find out that your assumption about their output was
  wrong, and it is cheaper to find that out now.
- If it changes a number, **the before and after from `make eval`**. "It feels
  better" is not a claim this project accepts.

## Changing an interface

The signatures in `schema.py` and the six component interfaces are **frozen for
the day**. If yours genuinely has to change:

1. Talk to the PM coordinators (team 6) *before* writing the code.
2. They tell every affected team.
3. Then you change it, in one PR, with the callers updated in the same PR.

An interface change that surprises another team costs them their afternoon.

## Owning your component

Each component has exactly one owning team. You may read everyone's code; you
change only your own — except by agreement.

When your stub becomes real, flip `STATUS = "stub"` to `STATUS = "real"` in your
module. `make board` reads it, and the coordinators copy the board onto the
whiteboard. Flipping it is the most public thing that happens all day; do not
flip it early.

## Before you push

```bash
make format     # fix the formatting so review is about substance
make check      # environment + tests
make scan       # no Nest data, no secrets
```

The pre-commit hooks run the last two automatically once you have done
`make hooks` — which everybody does, once, at the start of the day.

## When you are stuck

In this order:

1. **Fifteen minutes on your own.** Read your module's docstring; it lists what
   to check.
2. **Your team.** Say the problem out loud. Half the time that solves it.
3. **The team you are blocked on.** Usually it is a misunderstanding about what
   their function returns, and thirty seconds at their table fixes it.
4. **The PM coordinators.** They hold the question queue.
5. **Gianvito** — via the coordinators, so he is interrupted once per team rather
   than continuously.

You are never blocked waiting for another team's code. Every dependency you have
already resolves against a working stub. If you think you are blocked, come and
say so, because you are not and that is our fault for explaining it badly.

## Documentation

Your component's README section is a deliverable, not an afterthought. Write it
for a person who arrives in March 2027 having never seen the code, because that
is literally who will read it.
