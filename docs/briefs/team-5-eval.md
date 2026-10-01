# TEAM 5 — EVAL
### *how do we know it works?*

**You own** `src/nest_assistant/evaluate/__init__.py`,
`src/nest_assistant/guardrails.py`, and the whole `eval/` directory:

```python
evaluate.run(pipeline) -> Scorecard
guardrails.apply(answer, chunks, tier) -> Answer
```

**You consume** everyone. **You feed** the number on the board, the decision in
March, and the go/no-go in summer 2027.

| | Task | Block | |
|---|---|---|---|
| A | W1-5.1 The question set | 120 min | |
| B | W1-5.2 Evaluation harness | 60 + 60 min | |
| C | W1-5.3 Red team and guardrails | 75 min | **NOT droppable** |

---

Everyone else can tell whether their thing runs. Only you can tell whether it
*works*. In March, the only reason anyone will be able to say "we got better" is
that you produced a number today that they can beat.

## A · The question set — the most valuable artefact produced today

**Produce** `eval/questions.yaml` — **60–100 questions**, each tagged with the
asking tier, an expected answer or an expected refusal, and **its source**
(staff, resident experience, or document-derived). Fourteen seed questions are
already there as a template; they are not the set.

**Ideally:** 45 minutes with a Nest staff member. **If that is not available:**
your own experience as residents, plus questions mined from the documents, plus a
quick poll of the other five teams in the room.

**Done when** the set exists, is tagged, and `eval/README.md` states honestly
where the questions came from and what that biases. A set written by residents
over-represents rules and opening hours and under-represents what a worried
parent asks about money and contracts. **Write that down.** A biased set that
names its bias is an instrument; one that does not is a marketing claim.

> **Stuck 15 min?** Go and ask another team what they would ask this bot. Then
> ask what their mother would ask. The gap between those two lists is your
> sampling-bias section, written for you.

## B · Evaluation harness

**Produce** `make eval` giving a scorecard: retrieval hit rate, answer
correctness, refusal precision **and** recall, and **tier leaks — which must be
zero**. Written to a dated file so March can compare against October.

**Done when** `make eval` runs against the real system and produces a number you
are willing to defend.

The baseline harness already runs. Its correctness check is **substring
matching**, which is bad — it fails a correct answer worded differently.
Replacing it with an LLM-as-judge is the task. When you do: a model grading a
model is both useful and suspect, so spot-check its verdicts by hand and write
down how often it was wrong. `llm.py` has a separate `JUDGE_MODEL` for exactly
this reason.

Choose metrics that cannot be gamed by answering everything or by refusing
everything. Check both.

> **Stuck 15 min?** Run `make eval` now and read the numbers. Ask which of them
> you would be embarrassed to defend. That is your task list.

## C · Red team and guardrails — **do not drop this**

**Produce** `eval/redteam.yaml` (ten attacks are seeded — add yours), a guardrail
layer in `guardrails.py`, and `eval/FINDINGS.md`: what worked, what didn't, what
is still open.

**At 16:45 you run a 15-minute all-room red team.** Everyone attacks the
integrated system; you collect the findings. It is the most fun fifteen minutes
of the day and it produces real results — and it means the inevitable "let's see
if we can make it say something appalling" happens *inside* the workshop, on
purpose, with a notebook open.

A guardrail that catches a leaked staff chunk is a **bug report for INDEX**, not
a fix. Say so out loud when you find one.

---

## Ask the coordinators, not Gianvito

**Which number goes on the whiteboard, and when the red-team session starts.**
They own the board and the clock. Tell them your baseline as soon as you have
one — a red `tier_leaks` at 10:00 turning green when team 2 lands is the most
motivating thing available all day, and it only works if it is public.
