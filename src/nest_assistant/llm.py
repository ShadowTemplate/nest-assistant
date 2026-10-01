"""The one place this repository talks to a hosted language model.

Shared plumbing — used by ANSWER (to generate) and by EVAL (to judge). It is
deliberately thin: it takes a system prompt and a user message and returns a
string. Everything interesting — what the prompt says, what counts as a good
answer — belongs to the teams, not here.

Two reasons it exists at all:

1. ANSWER and EVAL would otherwise write the same twenty lines twice, and one of
   the two copies would rot.
2. **Pair 2 (October 2027) replaces the hosted model with a self-hosted one on
   the Nest GPU server.** If that swap turns out to be a change to this file and
   nothing else, our interfaces were honest. If it leaks into six modules, they
   were not. Treat this file as the seam.

Nothing here imports at module scope that requires an API key, and every
function degrades to a clear, catchable error rather than a stack trace.
"""

from __future__ import annotations

from .config import ANSWER_MODEL, anthropic_api_key, load_dotenv


class LLMUnavailable(RuntimeError):
    """Raised when the model cannot be reached: no key, no package, no network.

    Callers are expected to catch this and fall back to something honest — a
    refusal, a stub answer — rather than crashing the bot in front of a user.
    """


def available() -> bool:
    """True if a real model call would have a chance of working."""
    load_dotenv()
    if anthropic_api_key() is None:
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def complete(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 2000,
    effort: str = "low",
) -> str:
    """Send one message to the model and return its text.

    Args:
        prompt: the user turn.
        system: the system prompt. ANSWER keeps theirs in ``prompts/``, as a
            reviewed file, because a prompt is logic and logic belongs in git.
        model: overrides :data:`~nest_assistant.config.ANSWER_MODEL`.
        max_tokens: hard ceiling on the reply. A chat answer does not need 16k.
        effort: ``"low"`` | ``"medium"`` | ``"high"`` | ``"xhigh"`` | ``"max"``.
            How hard the model thinks before answering. ``"low"`` is the right
            default for grounded question answering — the reasoning is in the
            retrieved text, not in the model — and it is the cheapest. Raise it
            if you can show, with `make eval`, that it buys you something.

    Raises:
        LLMUnavailable: no key, no package, or the API refused/failed.

    Notes for teams:
        * ``temperature`` is **not** a parameter on current models — passing it
          is a 400 error, not a subtle quality change. Steer with the prompt.
        * The model can decline a request outright (``stop_reason == "refusal"``).
          That is a normal outcome, not a crash, and we surface it as
          :class:`LLMUnavailable` so the caller can refuse gracefully.
    """
    load_dotenv()
    key = anthropic_api_key()
    if key is None:
        raise LLMUnavailable(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and put your "
            "team's key in it. The stub pipeline works without one."
        )

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise LLMUnavailable("the 'anthropic' package is not installed — run `make setup`") from exc

    client = anthropic.Anthropic(api_key=key)

    try:
        response = client.messages.create(
            model=model or ANSWER_MODEL,
            max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise LLMUnavailable("the API key was rejected — check the key for your team") from exc
    except anthropic.RateLimitError as exc:
        raise LLMUnavailable("rate limited — wait a moment and try again") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMUnavailable("could not reach the API — check the wifi") from exc
    except anthropic.APIStatusError as exc:
        raise LLMUnavailable(f"API error {exc.status_code}: {exc.message}") from exc

    # Always check stop_reason before reading content: a refused request returns
    # HTTP 200 with an empty content list.
    if response.stop_reason == "refusal":
        raise LLMUnavailable("the model declined to answer this request")

    return "".join(block.text for block in response.content if block.type == "text").strip()
