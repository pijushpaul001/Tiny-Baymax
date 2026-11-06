# Tiny Baymax — v0.6.2 manual verification checklist

Use this checklist after automated tests pass. Do not put API keys, passcodes, or private health conversations in screenshots or logs.

## A. Local setup and closed-friends mode

- [ ] Set `BAYMAX_LLM=fake` and a non-empty `BAYMAX_TOKENS` value.
- [ ] Leave `BAYMAX_USER_CONTROLS=0` (the default) and start with `python -m server`.
- [ ] Open the app and confirm the connect screen is unchanged apart from the removed consent/review controls.
- [ ] Confirm the main chat has no Care & privacy panel, no clear-history arrow, and no in-app settings/data controls.
- [ ] Confirm the offline emergency card is present; no permanent emergency/disclaimer copy appears on the chat screen, and the connect-screen privacy note remains.
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


## G. Persona transcript check

- Run `python tools/persona_check.py` once with the real Gemini configuration to create `persona_check_output.md`. The script reads `GEMINI_API_KEY` and `BAYMAX_MODEL` through `Settings.from_env()`, uses a temporary database directory, and does not touch the app's real data.
- For a dry run without an API call, use `python tools/persona_check.py --llm fake --out persona_check_fake.md`.
- To enter the key without echoing it, use `read -s GEMINI_API_KEY; echo; export GEMINI_API_KEY`. Do not put a key directly in a command.
- **Never run this command with a key visible in shell history.**
- Paste back **the output file only** (`persona_check_output.md`). Do not paste the key, environment, or shell history.

- The default delay is 6 seconds after each model-backed reply. Override it with `--delay SECONDS`; for example, `python tools/persona_check.py --delay 2.5`. Use `--delay 0` to disable waiting. Negative values are rejected. Replies handled without the model (ritual, command and safety) do not trigger a delay.



## H. Face and voice — v0.6.11 phone checks

- [ ] Open the chat on the phone and confirm the white face is visible at the top of the conversation panel and blinks slowly.
- [ ] Scroll through a long conversation; confirm the face stays visible above the scrolling messages and the composer remains visible.
- [ ] Send `my head hurts`; confirm the face reacts after the assistant response.
- [ ] Confirm the top-bar Voice button starts on and can be switched off and on.
- [ ] With Voice on, confirm live assistant replies sound slow and soft.
- [ ] Use the microphone button; confirm recognized words fill the composer without being sent automatically.
- [ ] Enable the device's reduced-motion preference; confirm the face does not blink.
- [ ] Start a spoken reply, then send another message; confirm the previous speech is cancelled.

These are manual verification steps only. Leave every item unchecked until it has been tested on the target phone/browser. Do not include passcodes, tokens or private health conversations in screenshots or logs.
