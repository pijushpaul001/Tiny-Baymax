# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-11-04

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Active implementation branch:** `work/v0.6.6-persona-fixes`, created from current `main` at `a02502b7cfb565ae27b691143483bc1f673d838c`. The branch is 7 commits ahead of main; main was not modified.
- **Package version:** remains `0.6.5`. No version bump has been made; wait for the user's confirmation after tests and Actions are green.
- **Implemented scope:** health-term memory gate; plain how-are-you response and invented-body style guard; humour-off joke guidance; non-lecturing medical acknowledgement and retry guard; unstated-feelings/unsolicited-exit rules; optional fixed-string contraction cleanup. Each concern has a corresponding test change and log entry.
- **Local tests:** not run by the implementer for this branch. The owner-reported `127 OK` result on Python 3.14.2 was for v0.6.5 and does not verify these changes.
- **GitHub Actions:** the Python tests workflow for branch HEAD `a9b2b2324c58b2d96cf2828b5e21a222946dd1b1` was queued when this status was written; no conclusion is claimed. The earlier green result on `d6846aa` is not verification of this branch.
- **Real Gemini and device checks:** not run.
- **Scope exclusions:** no changes to `web/`, `baymax/detection.py` detection patterns, emergency/safety replies, shutdown ritual, or `baymax/llm/gemini.py`. Branch `work/v0.7.0-session-memory` was not modified.

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


## v0.6.4 chat fixes — S2 FAILURE TEXT

- Kept the existing blocked-response wording and the quota, auth, model-not-found and unavailable messages unchanged.
- Changed only `empty` and `other` failures to: "I had trouble answering. Please try again in a moment."
- Updated fixed-reply regression expectations.
- **Local verification:** tests were not run locally; no test count is claimed. CI and provider-side failure behavior remain unverified.


## v0.6.4 chat fixes — S3 STYLE GUARD

- Extended the existing single-retry style check to catch rating echoes after a rating was just supplied and invented body/mechanical wording (battery, lithium, charging, sensors, circuits).
- The retry adds explicit rewrite instructions; it remains limited to one retry.
- Added FakeLLM regressions that return a violating draft followed by a clean reply.
- **Local verification:** tests were not run locally; no test count is claimed. Retry behavior with a live Gemini model remains unverified.


## v0.6.4 chat fixes — S4 BRIEF

- Added an unconditional brief instruction to focus only on the problem currently being reported, without reviving an earlier different problem unless the user does.
- Added dependency-cue detection for "i need you", "you are all i have" and "don't leave me"; matching messages select reassure mode and add the requested trusted-person instruction.
- Added brief regressions for "i need you" and the current-problem scope rule.
- **Local verification:** tests were not run locally; no test count is claimed. Conversation-level behavior remains unverified against a live model.


## v0.6.4 chat fixes — S5 CLEANUP

- Removed the `temperature` argument from the Gemini generation configuration.
- Added the README note that Google AI Studio keys beginning with `AQ.` are normal API keys and are about 53 characters long.
- **Local verification:** tests and compilation were not run locally; no test count is claimed. Gemini request compatibility was not tested against the live API.

## v0.6.4 version metadata sync

- Deliberately synchronized `baymax.__version__` from `0.6.1` to `0.6.4`. The main-branch implementation log and source already contain the v0.6.4 S1–S5 chat-fix work; the package metadata had not been advanced with those changes. This is a metadata sync, not a silent version change or a new behaviour change.
- Added an API regression assertion that public `GET /api/health` returns the value of `baymax.__version__`.
- **Verification:** no local test execution has been performed in this environment. CI status for the new commit is pending.

## v0.6.4 export retention correction

- Changed `Store.export()` to query every message for the user directly, ordered by message ID. It no longer calls the bounded `history_with_time()` helper, which remains appropriate for conversation history windows.
- Repository grep/review found `MAX_MEMORIES` only at its declaration (automatic memory pruning had already been removed); `MAX_MESSAGES` was only declared and used by export. Removed both obsolete constants.
- Added a regression test that stores 305 messages and asserts export returns all 305 in insertion order.
- **Verification:** test code added; local tests have not been run in this environment. CI status for this commit is pending.


## v0.6.4 Gemini check findings

- **Owner-provided result:** the first real Gemini call worked in Codespaces using `gemini-3.5-flash-lite`; the response-quality check remains in progress.
- **Paste-in findings:** none supplied. The task's paste-in field contains only its placeholder, with no prompts, model replies, or specific problems.
- **Diagnosis / proposed fixes:** not applicable until concrete examples are provided. No Gemini behavior, prompt, detection pattern, safety logic, or shutdown behavior was changed for this check.
- **Verification:** the live call is owner-reported and not independently verified by this implementation. No quality conclusion is claimed.


## v0.6.5 — cleanup verification

- Bumped `baymax.__version__` to `0.6.5` after the retained-message export correction and its verification gate.
- **Verification:** local unittest **127 OK** (Python 3.14.2, Codespaces); GitHub Actions **green** on `d6846aa` (pre-version-bump commit); real Gemini and device checks **not run**.


## 2026-11-04 — v0.6.6 memory health gate

- Extended the memory keyword blocklist with the requested specific health terms; the blocklist is a keyword list and cannot be exhaustive.
- Added automatic and explicit-save rejection tests for the four requested examples, plus allowed stable-fact controls for dosa, guitar and wanting to be a doctor.
- **Verification:** tests added; local execution and Actions have not yet been run for this branch.


## 2026-11-04 — v0.6.6 how-are-you manner

- Replaced the vague instruction to answer simply with the plain, warm example: "I am well. Thank you for asking." The persona explicitly avoids programming/body-mechanics explanations and claims of real feelings.
- Extended the existing invented-body style guard to catch "functioning", "programmed" and "as designed"; added FakeLLM single-retry regressions.
- **Verification:** tests added; local execution and Actions have not yet been run for this branch.


## 2026-11-04 — v0.6.6 humour-off joke handling

- When the selected mode is playful but the deterministic style disables humour, the decision brief now forbids claiming inability to tell jokes and requests a gentle, non-joking observation instead.
- Added brief tests for humour-off and humour-allowed cases; humour-allowed behaviour remains unchanged.
- **Verification:** tests added; local execution and Actions have not yet been run for this branch.


## 2026-11-04 — v0.6.6 non-lecturing medical acknowledgement

- Added persona guidance to acknowledge a medicine or condition simply when no problem is reported, without assuming a prescription, dose or regimen.
- Added an "it is important to" style-guard pattern that triggers the existing single retry, with a FakeLLM violating-draft/clean-reply regression.
- **Verification:** tests added; local execution and Actions have not yet been run for this branch.


### Medical style-guard test assertion correction

- Corrected the retry test to inspect the system prompt from FakeLLM's documented call tuple `(system, history, user_msg)`.
- **Verification:** assertion corrected; test suite not run locally.


## 2026-11-04 — v0.6.6 assumption and exit wording

- Added persona and decision-brief rules not to attribute unstated pain or feelings to the user and not to offer ending the conversation unless the user asks.
- Added decision-brief regressions for "i need you" and "you are useless".
- **Verification:** tests added; local execution and Actions have not yet been run for this branch.


## 2026-11-04 — v0.6.6 fixed-string contraction cleanup

- Rewrote contractions in the emotional rating question, secret-redaction note and daily message-limit reply without changing the rating question's 0–10/skip shape or the greeting and shutdown question.
- Updated the existing secret-note exclusion assertion and added focused wording checks for the rating question and secret note.
- **Verification:** tests added/updated; local execution and Actions have not yet been run for this branch.


## 2026-11-04 — v0.6.6 verification status

- Consolidated current branch, version, scope and verification status. The package version remains 0.6.5 pending the user's confirmation.
- **Verification:** no local test run by the implementer; Actions was queued on the branch head at the time of this entry.
