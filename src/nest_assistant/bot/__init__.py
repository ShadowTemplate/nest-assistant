"""TEAM 4 — CHAT · *the part everyone can see*

You own::

    bot.run()

Your tasks
----------
W1-4.1  Telegram bot          -> a real bot, in a real chat, answering
W1-4.2  Identity resolution   -> see ``nest_assistant/identity``
W1-4.3  Conversation context  -> see ``bot/context.py``

You get the visible win of the day, and you get it early: nobody in the room can
see an embedding, but everybody can see a phone. When it works, say so loudly.

The rule that matters
---------------------
**The token comes from the environment.** ``TELEGRAM_BOT_TOKEN`` in ``.env``,
which is gitignored. Not in this file, not in a config file you commit, not
"just for a second to test it". A token in a public repo is a stranger running a
bot that speaks for Nest.

Stuck for 15 minutes?
---------------------
``make bot`` runs the console version below with the real pipeline behind it.
If that answers, your problem is Telegram, not the assistant — which is a much
smaller problem.
"""

from __future__ import annotations

import html
import re

from ..config import load_dotenv, telegram_bot_token
from ..identity import resolve
from ..pipeline import Pipeline
from ..schema import Answer
from . import context

OWNER = "TEAM 4 — CHAT"
INTERFACE = "bot.run()"
STATUS = "real"  # Telegram polling works. `make board` reads this.

WELCOME_IT = (
    "Ciao! Sono l'assistente di Nest. Posso rispondere a domande su prezzi, "
    "ammissioni, regolamento e vita in residenza.\n\n"
    "Comandi: /help per aiuto, /reset per ricominciare."
)

HELP_IT = (
    "Fammi una domanda in italiano, per esempio:\n"
    "• Quanto costa una camera singola?\n"
    "• Come si fa domanda di ammissione?\n"
    "• A che ora chiude la sala studio?\n\n"
    "Se non trovo la risposta nei documenti di Nest te lo dico, invece di "
    "inventarla."
)


def format_reply(answer: Answer) -> str:
    """Turn an :class:`~nest_assistant.schema.Answer` into a chat message.

    Citations are shown. A user who cannot see where an answer came from has to
    take it on faith, and this assistant has not earned that yet.
    """
    text = answer.text
    if answer.citations and not answer.refused:
        sources = ", ".join(answer.citations)
        text += f"\n\n📄 Fonti: {sources}"
    return text


_FOOTER_LINE = re.compile(r"^__(.+)__$", re.MULTILINE)


def to_telegram_html(text: str) -> str:
    """Render a reply for Telegram's HTML parse mode.

    Everything is escaped, then ANSWER's ``__footer__`` line becomes italics.
    Sent as plain text, Telegram would show the underscores literally.
    """
    return _FOOTER_LINE.sub(r"<i>\1</i>", html.escape(text, quote=False))


def handle_message(text: str, user_id: str, pipeline: Pipeline | None = None) -> str:
    """One message in, one reply out. Channel-independent on purpose.

    Telegram today, a phone line in 2028. Keep the logic here and the transport
    outside, and pair 2 gets a much easier job.
    """
    pipeline = pipeline or Pipeline()
    command = text.strip().lower()
    if command in {"/start", "start"}:
        return WELCOME_IT
    if command in {"/help", "help", "/aiuto"}:
        return HELP_IT
    if command in {"/reset", "reset"}:
        context.clear(user_id)
        return "Ok, ricominciamo. Fammi pure una domanda."

    tier = resolve(user_id)
    # The retriever sees one question at a time: "E la doppia?" must reach it as
    # "Quanto costa una camera doppia?".
    question = context.standalone_question(user_id, text)
    answer = pipeline.ask(question, tier)
    context.record(user_id, question, answer.text)
    return format_reply(answer)


# ---------------------------------------------------------------------------
# Telegram transport. No logic here: every reply comes from handle_message().
# ---------------------------------------------------------------------------
ERROR_IT = (
    "Scusami, ho avuto un problema tecnico e non riesco a rispondere adesso. "
    "Riprova tra poco; se serve, scrivi alla segreteria di Nest."
)


def _build_application(token: str, pipeline: Pipeline):
    import asyncio
    import logging
    import time

    from telegram.error import BadRequest
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    from .access import NOT_ALLOWED_IT, is_allowed
    from .chatlog import end_session, log_exchange

    log = logging.getLogger("nest_assistant.bot")

    async def reply(update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or update.effective_user is None or not message.text:
            return
        text = message.text
        if text.startswith("/"):  # "/start@NestBot" -> "/start"
            text = text.split("@", 1)[0]
        user_id = f"telegram:{update.effective_user.id}"
        started = time.monotonic()
        if not is_allowed(user_id):  # no pipeline call: unknown people cost nothing
            denial = NOT_ALLOWED_IT.format(user_id=user_id)
            try:
                await message.reply_text(denial)
            except Exception:  # noqa: BLE001
                log.exception("could not send the refusal")
            log_exchange(
                user_id=user_id,
                chat_id=message.chat_id,
                question=text,
                answer=denial,
                duration_ms=int((time.monotonic() - started) * 1000),
                denied=True,
            )
            return
        error: Exception | None = None
        try:
            await context.bot.send_chat_action(message.chat_id, "typing")
            answer = await asyncio.to_thread(handle_message, text, user_id, pipeline)
        except Exception as exc:  # noqa: BLE001 - a pipeline crash must not kill the bot
            log.exception("handle_message failed")
            error, answer = exc, ERROR_IT
        try:
            try:
                await message.reply_text(to_telegram_html(answer), parse_mode="HTML")
            except BadRequest:  # markup rejected: fall back to plain text
                await message.reply_text(answer)
        except Exception as exc:  # noqa: BLE001 - Telegram refused or timed out
            log.exception("could not send the reply")
            error = error or exc
        log_exchange(
            user_id=user_id,
            chat_id=message.chat_id,
            question=text,
            answer=answer,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=error,
        )
        if text.strip().lower() in {"/reset", "reset"}:  # same words handle_message accepts
            end_session(user_id)  # the /reset is the last line of the old session

    async def on_error(update, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.error("unhandled error in update handler", exc_info=context.error)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "help", "reset"], reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    app.add_error_handler(on_error)
    return app


def run_console(pipeline: Pipeline | None = None) -> None:
    """Console loop with the real pipeline behind it. Same handle_message()."""
    pipeline = pipeline or Pipeline()
    print("Nest Assistant — console mode. Ctrl-C to quit.\n")
    print(WELCOME_IT + "\n")
    while True:
        try:
            text = input("tu > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!")
            return
        if not text:
            continue
        if text in {"/quit", "/exit"}:
            print("Ciao!")
            return
        print(f"\nnest > {handle_message(text, user_id='console:local', pipeline=pipeline)}\n")


def run() -> None:
    """Start the bot: Telegram long-polling, or the console if there is no token."""
    import logging

    load_dotenv()
    token = telegram_bot_token()
    if token is None:
        print("TELEGRAM_BOT_TOKEN not set — running the console bot instead.\n")
        run_console()
        return

    logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
    # httpx logs full request URLs at INFO, and Telegram puts the token in the URL.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    app = _build_application(token, Pipeline())
    print("Telegram bot in polling mode. Ctrl-C to stop.")
    app.run_polling(allowed_updates=["message"], drop_pending_updates=True)


__all__ = [
    "run",
    "run_console",
    "handle_message",
    "format_reply",
    "to_telegram_html",
    "WELCOME_IT",
    "HELP_IT",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
