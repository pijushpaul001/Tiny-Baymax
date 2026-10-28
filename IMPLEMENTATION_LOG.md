# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-10-27

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Implementation snapshot:** v0.6.2 closed-friends mode
- **Active branch:** `work/v0.6.1-hardening`
- **Pull request:** PR #1 remains open and unmerged.
- **Automated verification:** not run locally for Round 5; GitHub Actions is the verification gate. Do not infer a test count from earlier snapshots.
- **CI:** must be checked on the new branch head separately.
- **Real Gemini / device verification:** not run.

## v0.6.2 — deliberate change to rule 9

2026-10-27 - Deliberate change to the non-negotiable rule on user data access (v0.6.2). The app is for the owner and one friend only, not published. Users no longer inspect, edit, export or delete stored data in the app, and the consent dialog and Care and privacy panel are removed. Stored data is kept without automatic deletion. Only the owner reads all users' data, with a read-only script on the server. Locked routes and commands are refused on the server, not only hidden in the page. Safety rules are unchanged: deterministic emergency replies, no diagnosis, secret redaction, and the satisfaction question before shutdown.

### Implementation

- Added `BAYMAX_USER_CONTROLS`, default `0`.
- Default server mode locks management routes with HTTP 403 and `code: "not_available"`.
- `/api/health`, `/api/session`, `/api/chat`, and `/api/session/end` remain available.
- Default slash commands other than `/quit` and `/exit` return exactly `That command is not available.` without changing data.
- `BAYMAX_USER_CONTROLS=1` preserves the previous management behaviour for tests/Codespaces.
- Removed the web Care & privacy panel, settings controls, clear-history control, consent dialog, review-consent control, localStorage consent gate, and the connect-time `consented_version` write.
- Kept chat, End session, rating chips/Skip, the existing offline emergency card, emergency line, and existing not-a-doctor line unchanged.
- Removed automatic 300-message and 100-memory pruning. The model history window remains 24 messages.
- Added `tools/export_all.py`, which opens SQLite read-only and prints all users' messages, memories, ratings, feedback, emotion and usage as JSON. It is not an HTTP route.
- Replaced consent/delete-path web tests with closed-friends UI and server-lock tests, compatibility-mode tests, retention tests, and read-only owner-export coverage.

## Existing safety behaviour retained

- Deterministic urgent/self-harm responses remain independent of Gemini.
- Safety persistence stores only `(message not saved)` plus Baymax's deterministic reply; raw emergency wording is not stored.
- Shutdown still asks the satisfaction question before final close.
- Secret redaction and detection hardening from prior rounds remain in place.

## Verification status

- `python -m unittest discover -s tests -t . -q` — **not run locally for Round 5**.
- `python -m compileall -q baymax server tests tools` — **passed**.
- `node --check web/app.js` — **passed**.
- `node --check web/sw.js` — **passed**.
- GitHub Actions on the new head: **not yet verified**.
- Browser/device/real Gemini verification: **not run**.

## Known limits

1. `BAYMAX_USER_CONTROLS=0` is the intended deployment mode; `1` exists for compatibility testing and Codespaces.
2. Owner export is intentionally a local/SSH tool and must never be exposed through the web API.
3. Stored messages and memories are retained indefinitely unless the owner performs an out-of-band database operation.
4. The model still receives only the configured recent-history window; retained history is not all sent to Gemini.
5. Real Gemini, phone/PWA, HTTPS/Tailscale and browser smoke verification remain separate manual gates.

## Historical record

Earlier Rounds 1–4 hardening work remains in the branch history and included rating persistence, shutdown handling, deterministic safety paths, secret redaction, authentication throttling, SQLite migrations, urgent-medical detection expansion, version assertions, and hosting documentation alignment.
