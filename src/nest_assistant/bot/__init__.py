"""TEAM 4 — CHAT · *the part everyone can see*

You own::

    bot.run()

Your tasks
----------
W1-4.1  Telegram bot          -> a real bot, in a real chat, answering
W1-4.2  Identity resolution   -> see ``nest_assistant/identity``
W1-4.3  Conversation context  -> droppable

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

from ..config import load_dotenv, telegram_bot_token
from ..identity import resolve
from ..pipeline import Pipeline
from ..schema import Answer

OWNER = "TEAM 4 — CHAT"
INTERFACE = "bot.run()"
STATUS = "stub"  # flip to "real" when Telegram works. `make board` reads this.

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
        return "Ok, ricominciamo. Fammi pure una domanda."

    tier = resolve(user_id)
    return format_reply(pipeline.ask(text, tier))


# ---------------------------------------------------------------------------
# TEAM 4 — REPLACE ME
# ---------------------------------------------------------------------------
def run() -> None:
    """Start the bot.

    Contract you must satisfy:

    * Long-polling is fine for W1 (no public URL, no webhook, no ngrok). Moving
      to a proper service on the Nest server is a W2 task — do not do it today.
    * ``/start``, ``/help``, ``/reset`` all work.
    * The token is read from the environment. Prove it: ``git grep`` your token
      and find nothing.
    * A crash in the pipeline must not kill the bot. Reply with something honest
      and stay up.
    * Every reply passes through :func:`handle_message`, so that the console
      version and the Telegram version cannot drift apart.

    The stub runs a console loop with the *real* pipeline behind it, so the rest
    of the room can talk to the assistant before you have a bot token working.
    """
    load_dotenv()
    if telegram_bot_token() is None:
        print("TELEGRAM_BOT_TOKEN not set — running the console bot instead.")
        print("(That is fine. Set it in .env when Team 4 is ready.)\n")
    else:
        print("TELEGRAM_BOT_TOKEN found, but bot.run() is still the stub.")
        print("TEAM 4: this is your task. Console loop for now.\n")

    pipeline = Pipeline()
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


__all__ = [
    "run",
    "handle_message",
    "format_reply",
    "WELCOME_IT",
    "HELP_IT",
    "OWNER",
    "INTERFACE",
    "STATUS",
]
