# TEAM 3 — ANSWER
### *retrieved text in, trustworthy Italian out*

**You own** `src/nest_assistant/answer/__init__.py` and
`prompts/answer_system.it.md`:

```python
generate(q: str, chunks: list[Chunk], lang: str) -> Answer
```

**You consume** chunks from INDEX — their stub works until theirs is real.
**You feed** the bot, and therefore every human who ever talks to this thing.

| | Task | Block | |
|---|---|---|---|
| A | W1-3.1 Grounded generation | 120 min | |
| B | W1-3.2 Refusal and abstention | 105 min | **the most important task of the day** |
| C | W1-3.3 Answer quality pass | 60 min | **droppable** |

---

## Two things that are not negotiable

1. **The system prompt lives in `prompts/answer_system.it.md`, not in a string in
   your code.** A prompt is logic: it gets reviewed, versioned and blamed like
   any other logic. There is a test that checks this.
2. **Every claim comes from `chunks`.** If the chunks do not contain the answer,
   the correct output is a refusal.

## A · Grounded generation

**Produce** a working `generate()`; the system prompt as a reviewed file;
citations returned as chunk ids.

**Done when** a real question about Nest gets a correct Italian answer whose
citation points at the document a human would have cited.

`llm.py` already talks to the model — one function, `complete(prompt, system)`.
Do not write your own client: in October 2027 that file becomes a self-hosted
model on Nest's GPUs, and the swap only stays one line if everyone goes through
it.

> **Stuck 15 min?** Run `make demo` and read what the stub prints, then read
> `prompts/answer_system.it.md`. If the problem is that INDEX is giving you
> rubbish chunks, that is a real finding — go and tell them, do not paper over it
> in your prompt.

## B · Refusal and abstention

Make the assistant say *"non lo so — scrivi alla segreteria"* instead of
inventing something plausible.

**Produce** a confidence/threshold mechanism; a prompt strategy; a test set of
questions the corpus genuinely cannot answer; and the refusal message text,
written with care **because parents will read it**.

**Done when** every question in the unanswerable set is refused, **and** no
question in the answerable set is refused. Both failure directions get measured —
a system that refuses everything is not cautious, it is broken.

> **Stuck 15 min?** `eval/questions.yaml` already contains three questions marked
> `expect: refusal`. Start there, then go and get more from EVAL.

> This is the intellectual peak of the day. Students arrive believing AI's
> problem is that it is not smart enough. You are about to find out that its
> problem is that it does not know what it does not know — and that engineering
> that boundary is human work.

## C · Answer quality pass *(droppable)*

Length, tone and formatting for a chat window. A question that spans two
documents. A question the user asked badly.

**Done when** you would be comfortable showing the answer to a parent on a phone.

---

## Not yours to change

`Answer` in `schema.py`. `generate()` never raises — if the model is unreachable,
you refuse, and the bot stays up saying something honest.

## Ask the coordinators, not Gianvito

**The wording of the refusal message, and anything about the assistant's voice.**
It is a product decision about how Nest sounds to a worried parent, not a
technical one, and it needs to be the same everywhere. Draft it, then take the
draft to them.
