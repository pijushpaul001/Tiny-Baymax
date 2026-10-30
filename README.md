# Tiny Baymax

A private personal AI companion: a Baymax-style healthcare companion you talk to from your phone.
Python server + installable web app. Gemini is the language brain; Python enforces everything that must be reliable
(greeting, shutdown ritual, 0-10 ratings, memory rules, secret redaction, safety replies).

## v0.6.2 — closed-friends mode

Tiny Baymax is intended for two users: the owner and one friend. The default `BAYMAX_USER_CONTROLS=0` removes in-app
memory, rating, settings, history, export and delete controls and enforces the same restriction on the server. The app
keeps chat, End session, rating chips/Skip, the offline emergency card, the emergency line, and the existing not-a-doctor line.

Stored messages and memories are kept without automatic 300-message/100-memory deletion. The model still receives only
the latest 24 messages. The owner can inspect all users' stored data with the read-only `tools/export_all.py` script over SSH;
it is not exposed through HTTP. `BAYMAX_USER_CONTROLS=1` restores the old management behaviour for tests and Codespaces.

## Quick start

1. Python 3.10 or newer:
   ```
   pip install -r requirements.txt
   cp .env.example .env
   ```
2. Set:
   - `GEMINI_API_KEY` on the server. Google AI Studio now issues keys starting with `AQ.`; these are normal API keys and are about 53 characters long.
   - `BAYMAX_TOKENS=owner=<long-random-passcode>,friend=<long-random-passcode>`
   - leave `BAYMAX_USER_CONTROLS=0` for the normal two-user deployment
3. Run:
   ```
   python -m server
   ```
4. Open the configured HTTPS/Tailscale address on the phone and connect with the server passcode.

For a no-cost local smoke test, set `BAYMAX_LLM=fake`.

## Phone hosting

Use the project hosting path:

- **Cloud VM + Tailscale**: keep Baymax bound to `127.0.0.1`, then use `tailscale serve --bg 8080` on the VM.
  Open the resulting private HTTPS address on the phone. Keep `data/` on persistent VM storage and run one always-on server process.

## Data and owner access

The SQLite database is `data/baymax.db`. It stores per-user messages, memories, emotion, settings, ratings, feedback and usage.
Closed-friends mode does not automatically prune old messages or memories. Safety turns still store only the neutral
`(message not saved)` placeholder plus Baymax's deterministic safety reply; the raw emergency wording is not stored.

Owner-only export:

```bash
python tools/export_all.py data/baymax.db
```

The script opens SQLite read-only and prints all users' messages, memories, ratings, feedback, emotion and usage as JSON.
It is intended for SSH use on the VM and is never an HTTP endpoint.

## Project layout

```
baymax/            brain, decision, safety, persistence
server/             standard-library HTTP server and JSON API
web/                installable phone web app
tools/export_all.py owner-only read-only data export
tests/              regression tests
docs/               architecture and manual verification
```

## Safety

- The Gemini key stays on the server.
- Private API requests require a user passcode; the health check is public.
- Keys, passwords and card-like numbers are redacted before model/storage use.
- Deterministic emergency/self-harm replies do not depend on Gemini.
- Baymax is not a doctor, medical device, or emergency service.

## Compatibility flag

`BAYMAX_USER_CONTROLS=1` restores the previous in-app data controls and management commands for tests/Codespaces.
The normal deployment default is `0`.

## Development

Run:

```bash
python -m compileall -q baymax server tests tools
python -m unittest discover -s tests -t . -v
```

See [`docs/MANUAL_TEST.md`](docs/MANUAL_TEST.md) for the fake-model, server-lock, owner-export, Gemini and phone checks.

**Emergency detection limitation:** Detection is deliberately fail-safe. Informational and third-party mentions can also trigger the safety response.
