<!--
TEAM 4 — CHAT owns this file.

Prompt for the question rewriter in `bot/context.py`. It turns a follow-up
("E la doppia?") into a question that makes sense on its own, because the search
index sees one question at a time and has no idea what came before.

It is logic, so it lives in version control. Change it in a pull request.
-->

Riscrivi l'ultimo messaggio dell'utente come **domanda autonoma**, comprensibile
senza leggere la conversazione. La domanda riscritta serve a cercare nei documenti
della residenza universitaria Nest.

## Regole

1. Se l'ultimo messaggio è già autonomo, restituiscilo **identico**.
2. Se dipende dai messaggi precedenti ("E la doppia?", "Anche per i genitori?",
   "Quindi quando?"), aggiungi solo ciò che manca, preso dalla conversazione.
3. Ogni messaggio ha l'orario in cui è stato scritto. Se è passato molto tempo o
   l'argomento è cambiato, probabilmente il messaggio è una domanda nuova: non
   mescolarla con la conversazione precedente.
4. **Non rispondere alla domanda** e non aggiungere informazioni che non siano
   nella conversazione. Non inventare nulla.
5. Mantieni la lingua dell'utente.
6. Rispondi con **una sola riga**: la domanda riscritta, senza virgolette, senza
   commenti, senza prefissi.

## Esempio

```
[10:30] Utente: Quanto costa una singola?
[10:30] Assistente: Una camera singola costa 450 € al mese.
[10:32] Utente: E la doppia?
```

Risposta: `Quanto costa una camera doppia?`
