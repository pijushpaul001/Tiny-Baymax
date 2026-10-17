# Architecture

## Principle
The model is the language brain. Python is the control system. Anything safety-critical is decided by deterministic
Python before or after the model is called, never by the model alone.

## Layers (each only calls the one below)

```
Phone app (web/)            chat screen, face, voice, settings
      | HTTPS + passcode
server/app.py  server/api.py  server/auth.py      transport only, no behaviour
      |
baymax/service.py  ChatService                    commands, shutdown ritual, sessions, saving
      |
baymax/brain.py    BaymaxBrain                    decide -> generate -> validate
   |-- baymax/decision.py   DecisionLayer         detection, ratings, emotion, memory, mode (no I/O)
   |-- baymax/llm/*         LLM adapter           Gemini or FakeLLM (swappable)
   '-- baymax/safety.py     redaction + memory gate
      |
baymax/storage.py  Store (SQLite)                 per-user memories, history, emotion, ratings, feedback, usage
```

## One chat message, step by step

1. The app sends `POST /api/chat {"message": "..."}` with the passcode header.
2. `Auth` maps the passcode to a user id. Everything below is scoped to that user.
3. `ChatService.handle` checks, in order: shutdown ritual state, quit words, `/commands`.
4. Otherwise it is a conversation turn:
   1. Daily limit check.
   2. `redact_secrets`: keys/passwords are hidden. A message that is only a secret is answered without the model.
   3. Load emotion, settings, recent history and memories for this user.
   4. `DecisionLayer.decide`:
      understand context -> detect difficulty -> severity need -> update emotion -> check memory -> choose mode.
      Red flags and 0-10 rating questions are answered by Python directly (the model is not called).
      Otherwise it builds a "decision brief" that tells the model the mode, tone, question budget and health rules.
   5. `BaymaxBrain` calls the model, validates the JSON, retries once if the reply used banned filler or clingy wording,
      trims a trailing question when the question budget is zero, and passes any proposed memory through `memory_gate`.
   6. `ChatService` saves the exchange, emotion, rating and memory, and returns the reply plus the new emotion values.
5. The app shows the reply, speaks it if enabled, and moves the face (eye size and blink rate follow the emotion).

## Data (SQLite, data/baymax.db)

| Table | Purpose |
|---|---|
| memories | stable facts only (max 100 per user), gated by `memory_gate` |
| messages | recent conversation (last 300 per user); the model sees the last 24 |
| emotion | six simulated values per user |
| settings | auto_memory, speak |
| ratings | self-reported 0-10 values over time (not a diagnosis) |
| feedback | answers to "What could I have done better?" (never memory) |
| usage | messages per user per day |

Session state (open rating question, shutdown ritual step) is held in memory and resets if the server restarts.

## Security notes
- Passcodes compared in constant time; failed attempts delayed.
- Static files restricted to `web/`; strict Content-Security-Policy; no inline scripts.
- The UI writes messages with `textContent`, never HTML.
- Request body capped at 16 KB, message at 2000 characters.
- Server logs do not record message content.

## Extension points
- New model: add an adapter with `generate(...)`.
- New client (voice device, robot): call `ChatService.handle(user_id, text)`; nothing else is needed.
- New command: add a branch in `ChatService._command`.
- New detection rule: add a pattern in `detection.py` and a test in `tests/`.

## Known limits
- Detection is keyword based, so unusual phrasings can be missed. Use `/debug` to see why a turn went the way it did.
- The server is a simple threaded standard-library server, fine for one person or a few friends. If it ever needs more,
  `server/api.py` has no web-framework code and can be moved to FastAPI unchanged.
- Spoken input depends on the phone browser's speech support.

## Roadmap
- V0.7: reminders and notifications, richer settings, spoken-number handling for ratings.
- V0.8: tools (calendar, weather, search), conversation summaries as a second memory layer.
- V0.9: semantic memory, better voice delivery.
- V1.0: stable personal release; optional native wrapper.
