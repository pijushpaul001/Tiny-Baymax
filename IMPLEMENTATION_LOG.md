# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-10-28

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Implementation snapshot:** v0.6.3 Gemini-ready (R3-6 and R3-7 implemented on a fresh branch from `main`).
- **Active branch:** `work/v0.6.3-gemini-ready`, created from the updated `main`, not the old work branch.
- **Previous PR:** PR #1 was squash-merged into `main`; the prior status above was stale.
- **Automated verification:** not run locally for v0.6.3. No test count is claimed.
- **CI:** not verified for the v0.6.3 branch head.
- **Real Gemini / device verification:** not run.

## v0.6.3 — Gemini-ready (R3-7 and R3-6)

### R3-7 — merge same-role messages

- Added the SDK-free `build_gemini_messages` helper and wired it into `GeminiAdapter.generate`.
- Consecutive user/model messages are joined with a blank line; leading model messages are removed; the new user message is appended or merged with the final user turn.
- Added no-network unit tests for leading assistant messages, consecutive user messages, a history ending in a user message, empty history, role alternation and final-user-turn behavior.

### R3-6 — stable LLM error codes

- Added SDK-free `classify_llm_error` and `LLMError.code`.
- Gemini API errors are wrapped without copying provider exception text. Safety-filtered and empty responses get explicit `blocked` and `empty` codes.
- The service maps codes to fixed user-facing replies, exposes only the code and exception type in the detail field/log, and adds the existing emergency guidance line while a safety hold is active.
- Kept the existing rating persistence path on model failure.
- Added no-network tests for status-code classification, timeout/network failures, blocked/empty/other classification, fixed replies, secret-text non-disclosure, safety-hold emergency guidance, and Gemini safety metadata.
- **Verification:** tests have not been run locally; CI and live Gemini/device behavior remain unverified.

## v0.6.3 follow-up — R3-6b

- A 400 response is classified as `auth` only when its exception text contains `api key not valid` or `API_KEY_INVALID` (case-insensitive); other 400 responses remain `other`.
- Exception text is inspected only for classification and is not included in replies, details, or logs.
- Added focused classification tests. Tests were not run locally; no test count is claimed.

## v0.6.3 follow-up — additional Gemini blocked reasons

- Added `BLOCKLIST` and `SPII` to blocked Gemini candidate finish reasons.
- Added a focused `BLOCKLIST` regression test. Tests were not run locally; no test count is claimed.

## v0.6.3 follow-up — R3-6c

- Added shared `safety_hold_active(turn, hold_until)` logic using an inclusive comparison and used it in both the decision layer and LLM failure reply path.
- Added coverage for the inclusive boundary and for three failure replies during a safety hold followed by a fourth without the emergency line. Tests were not run locally; no test count is claimed.

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


## v0.6.4 chat fixes — S1 EXIT

- Expanded short whole-message exit recognition to remove the specified filler words before matching farewell phrases, with a six-word input limit.
- Preserved existing exit phrases and the existing safety-hold exit path.
- Added regression cases for the requested polite farewells and ordinary sentences containing farewell words.
- **Local verification:** tests were not run locally; no test count is claimed. GitHub Actions and safety-hold regression execution remain unverified.
