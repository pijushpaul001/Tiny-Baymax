# Tiny Baymax

A private personal AI companion: a Baymax-style healthcare companion you talk to from your phone.
Python server + installable web app. Gemini is the language brain; Python enforces everything that must be reliable
(greeting, shutdown ritual, 0-10 ratings, memory rules, secret redaction, safety replies).

Version 0.6.1 hardening work: the earlier Colab prototype is now organized as a Python server, SQLite store, JSON API, regression tests and installable web app. Review the implementation log before treating this snapshot as production-ready.

## Quick start (about 5 minutes)

1. Python 3.10 or newer. In this folder:
   ```
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. Open `.env` and set:
   - `GEMINI_API_KEY` (your key, stays on the server)
   - `BAYMAX_TOKENS=me=<a long random passcode>`. The sample is blank by default. Make one with
     `python -c "import secrets; print(secrets.token_urlsafe(24))"`
3. Run it:
   ```
   python -m server
   ```
4. Open http://127.0.0.1:8080 on the same computer, enter your passcode, and talk.

No API key yet? Set `BAYMAX_LLM=fake` in `.env` to try the whole app with a stand-in brain.
Prefer the terminal? `python -m baymax.cli`.

Run the tests any time: `python -m unittest discover -s tests -t .`

## Using it on your phone

Voice input, speech output and "install to home screen" need HTTPS (or localhost). Use the project hosting path:

- **Cloud VM + Tailscale**: install Tailscale on the VM and the phone. Keep Baymax bound to `127.0.0.1`, then run
  `tailscale serve --bg 8080` on the VM and open the `https://<your-vm>.<tailnet>.ts.net` address on the phone.
  This keeps the app private to your Tailscale network and provides HTTPS without exposing the Baymax server directly.
  Keep `data/` on the VM's persistent disk and run the server as a single always-on process.

On the phone: open the address, then "Add to Home screen" (Android Chrome) or Share > "Add to Home Screen" (iPhone Safari).
Voice input works in Chrome on Android. iPhone Safari support for speech input is limited; typing and spoken replies work.

## What is in the folder

```
baymax/            the brain (no web code in here)
  decision.py        decides WHAT Baymax does, before the model is called
  detection.py       difficulty, red flags and rating detection
  emotion.py         simulated emotion state and how it changes behaviour
  safety.py          secret redaction and the long-term memory gate
  persona.py         personality text and the structured-output schema
  brain.py           decision layer -> model -> validation
  service.py         commands, shutdown ritual, sessions, saving
  storage.py         SQLite (one file: data/baymax.db)
  llm/gemini.py      the only file that knows about Gemini
server/            tiny web server (standard library only) + JSON API
web/               the phone app (installable web app)
tests/             regression tests (run with unittest)
docs/ARCHITECTURE.md
```

## Privacy and safety, in plain words

- Your Gemini key lives only in `.env` on the server. It is never sent to the app or saved in the database.
- The server only listens on your own computer unless you change `BAYMAX_HOST`.
- Every private API request needs your passcode. Repeated wrong guesses from one client are temporarily locked out; the health check is public.
- If you deliberately place a trusted reverse proxy on the same machine, set `BAYMAX_TRUSTED_PROXY=1` so login lockout can use the final validated `X-Forwarded-For` address. Leave it off otherwise; forwarded headers are ignored unless the direct peer is loopback.
- Keys, passwords and card-like numbers you type are hidden before anything is sent to Gemini or saved.
- When an emergency/safety response occurs, Baymax best-effort saves the reply with a neutral `(message not saved)` placeholder. Your original emergency wording is not saved in that exchange, but the record still indicates that a safety response occurred.
- Health details, moods and private relationship facts never become long-term memories automatically.
- In the app's settings you can see every memory and rating, remove them, download all your data, or delete everything. Deleting everything also attempts to purge all pre-migration database snapshots in the data directory; if a snapshot cannot be removed, the response warns you so you can retry or remove it manually.
- Messages go to Google's Gemini service. On the free tier Google may use content to improve its products, so switch your
  Google project to the paid tier before sharing the app with anyone else. Check Google's current terms.
- Baymax is not a doctor and the app is not a medical device.

## Changing things

- **Different model:** change `BAYMAX_MODEL` in `.env`. To use another provider, add a file next to `llm/gemini.py` with a
  `generate(system, history, user_msg, schema)` method and select it in `server/app.py`.
- **Emergency number text:** `BAYMAX_EMERGENCY_HINT`.
- **Personality:** edit `baymax/persona.py`.
- **Message limit:** `BAYMAX_MAX_PER_DAY`.

## Development status

The v0.6.1 hardening snapshot includes targeted regression tests. Run them locally with:

```bash
python -m compileall -q baymax server tests
python -m unittest discover -s tests -t . -v
```

See [`docs/MANUAL_TEST.md`](docs/MANUAL_TEST.md) for the real Gemini and phone checks that cannot be proven by automated tests. Real Gemini use and phone access must be verified on your own configured server before relying on them.


**Emergency detection limitation:** Detection is deliberately fail-safe. Informational and third-person mentions can also trigger the safety response.
