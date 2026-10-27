# Architecture

## Principle
The model is the language brain. Python is the control system. Anything safety-critical is decided by deterministic
Python before or after the model is called, never by the model alone.

## Closed-friends mode (v0.6.2)
The default server setting is `BAYMAX_USER_CONTROLS=0`. The web app exposes chat, session ending, rating chips/Skip,
the offline emergency card, the emergency line, and the existing not-a-doctor line. It does not expose in-app data
management.

The restriction is enforced in `server/api.py`, not just by hiding UI. When controls are disabled, management routes for
memories, ratings, settings, emotion, history and data return HTTP 403 with `code: "not_available"`. `/api/health`,
`/api/session`, `/api/chat`, and `/api/session/end` remain available. Slash commands other than `/quit` and `/exit`
return `That command is not available.` without changing data. Setting `BAYMAX_USER_CONTROLS=1` restores the previous
management behaviour for tests and Codespaces.

## Layers

```
Phone app (web/)            chat, rating chips, shutdown, emergency UI
      | HTTPS + passcode
server/app.py  server/api.py  server/auth.py      transport and server-side access policy
      |
baymax/service.py  ChatService                    commands, shutdown ritual, sessions, saving
      |
baymax/brain.py    BaymaxBrain                    decide -> generate -> validate
   |-- baymax/decision.py   DecisionLayer         detection, ratings, emotion, memory, mode
   |-- baymax/llm/*         LLM adapter           Gemini or FakeLLM
   '-- baymax/safety.py     redaction + memory gate
      |
baymax/storage.py  Store (SQLite)                 per-user memories, history, emotion, ratings, feedback, usage
      ^
      | read-only owner access
 tools/export_all.py
```

## One chat message

1. The app sends `POST /api/chat` with the passcode header.
2. `Auth` maps the passcode to a user id.
3. The server rejects locked management commands before they reach `ChatService`.
4. `ChatService.handle` runs deterministic safety, rating and shutdown logic before model generation.
5. Normal turns use redaction, recent history, memories, emotion and the decision/model layers.
6. The exchange, emotion, rating and approved memory are persisted. Safety turns persist only `(message not saved)` plus
   Baymax's deterministic reply; the raw emergency wording is not stored.

## Data retention

SQLite keeps stored messages and memories without automatic 300-message/100-memory pruning. The model still receives only
the most recent 24 messages through `Store.history(uid, 24)` and the brain's configured history window.

The app no longer exposes history clearing, memory deletion, export, or delete-all controls in closed-friends mode.
Those management routes remain implemented for the compatibility mode and are locked by default.

## Owner export

`tools/export_all.py` opens `data/baymax.db` through SQLite's read-only URI mode and prints all users' messages,
memories, ratings, feedback, emotion and usage as JSON. It is intended to be run over SSH on the VM and is not an HTTP
route.

## Security notes
- Passcodes are compared in constant time; failed attempts are delayed.
- Static files are restricted to `web/`; strict Content-Security-Policy; no inline scripts.
- The UI writes messages with `textContent`, never HTML.
- Request body is capped at 16 KB and messages at 2000 characters.
- Server logs do not record message content.
- Owner export is read-only and is not exposed through the API.

## Known limits
- Detection is keyword based, so unusual phrasings can be missed.
- The server is a simple threaded standard-library server, suitable for this two-user private deployment.
- Spoken input depends on the phone browser's speech support.

## Extension points
- New model: add an adapter with `generate(...)`.
- New client: call `ChatService.handle(user_id, text)`.
- New detection rule: add a pattern in `detection.py` and a test in `tests/`.
