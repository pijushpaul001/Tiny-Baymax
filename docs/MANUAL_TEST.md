# Tiny Baymax — v0.6.2 manual verification checklist

Use this checklist after automated tests pass. Do not put API keys, passcodes, or private health conversations in screenshots or logs.

## A. Local setup and closed-friends mode

- [ ] Set `BAYMAX_LLM=fake` and a non-empty `BAYMAX_TOKENS` value.
- [ ] Leave `BAYMAX_USER_CONTROLS=0` (the default) and start with `python -m server`.
- [ ] Open the app and confirm the connect screen is unchanged apart from the removed consent/review controls.
- [ ] Confirm the main chat has no Care & privacy panel, no clear-history arrow, and no in-app settings/data controls.
- [ ] Confirm the offline emergency card, emergency line, and existing not-a-doctor line remain present.
- [ ] Confirm no consent dialog appears and connecting does not require browser localStorage consent.
- [ ] Confirm `/api/health` is public and the version is reported correctly.

## B. Server-side lock checks

- [ ] With `BAYMAX_USER_CONTROLS=0`, confirm each memories, ratings, settings, emotion, history/data management route returns HTTP 403 with `code: not_available`.
- [ ] Confirm `/api/health`, `/api/session`, `/api/chat`, and `/api/session/end` still work.
- [ ] Send `/help`, `/state`, `/memories`, `/forget`, `/clear`, `/memory-off`, and another slash command through chat; each must reply exactly `That command is not available.` and leave stored data unchanged.
- [ ] Confirm `/quit` and `/exit` still start the satisfaction ritual.

## C. Conversation and safety

- [ ] Send `My head hurts`; confirm the 0–10 pain question and Skip control.
- [ ] Select a rating; confirm the rating is stored even though the Ratings panel is unavailable.
- [ ] Run the shutdown ritual and confirm the satisfaction question and feedback path still work.
- [ ] Trigger an urgent safety phrase; confirm the deterministic safety reply still takes priority.
- [ ] Confirm emergency wording is not stored verbatim; only the placeholder and Baymax reply are persisted.
- [ ] Send enough messages to exceed the old 300-message boundary and enough memories to exceed 100; confirm older rows are retained while the model still receives only the recent 24-message window.

## D. Owner export

- [ ] Create a disposable SQLite database containing two users with messages, memories, ratings, feedback, emotion and usage.
- [ ] Run `python tools/export_all.py <path-to-db>` over SSH and confirm both users appear in JSON.
- [ ] Confirm the database bytes/hash are unchanged before and after the export.
- [ ] Do not expose `export_all.py` through HTTP.

## E. Compatibility mode

- [ ] Set `BAYMAX_USER_CONTROLS=1` in a test/Codespaces environment.
- [ ] Confirm the previous management routes and slash commands work as before.
- [ ] This flag exists for tests and Codespaces; the VM's default remains `0`.

## F. Real Gemini and phone verification

- [ ] Set `BAYMAX_LLM=gemini` and configure `GEMINI_API_KEY` only in server `.env`.
- [ ] Verify the configured model identifier is currently available and permitted.
- [ ] Access the server from the phone over the trusted HTTPS/Tailscale route.
- [ ] Test chat, rating chips/Skip, shutdown, service-worker behaviour, and offline error state.
- [ ] Record only non-sensitive outcomes in `IMPLEMENTATION_LOG.md`.

## Test limits

Automated fake-model tests cannot prove real Gemini availability, current model permissions, mobile installation, microphone/speech support,
HTTPS routing, or actual phone behaviour. Do not mark those checks as passed until performed in the configured environment.
