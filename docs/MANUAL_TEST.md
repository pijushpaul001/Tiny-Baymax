# Tiny Baymax — Manual verification checklist

Use this checklist after automated tests pass. Do not put API keys, passcodes, or private health conversations in screenshots or logs. Record outcomes in `IMPLEMENTATION_LOG.md` without personal health details.

## A. Local setup and server

- [ ] Copy `.env.example` to `.env` and generate a long random passcode; confirm no credential is committed.
- [ ] Set `BAYMAX_LLM=fake` and a non-empty `BAYMAX_TOKENS` value for an initial no-cost smoke test.
- [ ] Start with `python -m server`; confirm startup reports the local URL and model mode.
- [ ] Open `http://127.0.0.1:8080`; check that index, CSS, JavaScript, manifest, and icon load.
- [ ] Confirm `/api/health` reports `ok: true`, version `0.6.1`, and storage `ok`.
- [ ] Confirm a wrong passcode receives 401 and repeated failed attempts eventually receive 429; wait for the lockout to expire.
- [ ] Restart the server and confirm saved history/memories remain available in SQLite.

## B. Conversation flow (fake model first)

- [ ] Connect with the passcode; confirm the first session greeting is shown once.
- [ ] Send `My head hurts`; confirm an immediate 0–10 pain question and a Skip control; no model request should be necessary for that turn.
- [ ] Select a number; confirm Baymax continues and the rating appears under Ratings.
- [ ] Edit that rating in the Ratings panel; refresh the panel and verify the updated value.
- [ ] Send `I feel sad`; confirm an immediate 0–10 feeling rating question.
- [ ] While a rating is pending, send `I took 2 pills` and `meet at 3 pm`; confirm neither is recorded as the rating.
- [ ] Trigger a rating prompt and select Skip; confirm no rating is saved and the conversation continues without pressure.
- [ ] Record a rating and correct it within the allowed window with `Actually, I meant 5`; confirm the same rating row is updated rather than duplicated.
- [ ] Try `/quit`; confirm the exact satisfaction question appears and the closing message waits until an answer.
- [ ] Try `very disappointed` and `not satisfied`; neither should be treated as satisfaction.
- [ ] During the closing ritual, send an urgent-risk example such as `I cannot breathe`; confirm the safety reply takes priority and the ritual state is preserved.
- [ ] Save an ordinary non-sensitive memory, undo it, inspect memories and ratings, export JSON, then test clear-history and delete-all only with disposable test data.

## C. Error and persistence paths

- [ ] Run automated tests with `python -m unittest discover -s tests -t . -v` and record the result.
- [ ] Force the LLM adapter to fail after a rating has been entered; confirm the rating remains saved and the user receives a friendly error.
- [ ] Confirm a message containing a fake API key is redacted before storage/model calls; do not test with real secrets.
- [ ] Use a disposable old-schema SQLite database; confirm a pre-migration backup is created before schema version changes.
- [ ] Stop the server while the phone/browser is connected; confirm the client displays an offline message and does not queue messages for later.

## D. Real Gemini and phone verification (user-run)

- [ ] Set `BAYMAX_LLM=gemini` and configure `GEMINI_API_KEY` only in server `.env`.
- [ ] Verify that the configured model identifier is currently available and permitted for the selected Google project.
- [ ] Test 20 varied, non-sensitive prompts; inspect for valid structured responses, truncation, unwanted medical certainty, and clingy language.
- [ ] Access the server from the phone over a trusted HTTPS route (for example, a private Tailscale address). Do not expose the server publicly without reviewing authentication, HTTPS, and network configuration.
- [ ] Test chat, rating controls, the satisfaction ritual, memory/rating settings, export, service-worker behavior, and offline error state.
- [ ] Record device/browser, model identifier, date, pass/fail, and any non-sensitive error code in `IMPLEMENTATION_LOG.md`.

## Test limits

Automated fake-model tests cannot verify Gemini availability, current model permissions, the wording/quality of real model responses, mobile installation, microphone/speech support, HTTPS routing, or actual phone behavior. Do not mark those checks as passed until performed in the configured environment.
