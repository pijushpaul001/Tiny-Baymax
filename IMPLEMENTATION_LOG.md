# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-11-04

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Active implementation branch:** `work/v0.6.7-persona-examples`, created from updated `main` at `2624c9434ea6b2962b181d27a7f39f173754ea3a` (v0.6.6 merged).
- **Package version:** remains `0.6.6`; no v0.6.7 version bump has been made.
- **Implemented scope:** exact owner-supplied persona rewrite; style-guard additions and AI-companion non-match regression; isolated five-group persona check script and pure reply flagger; manual test instructions; CLI trace display; the persona checker records when ChatService supplies no trace. Every task has a corresponding test change and log entry.
- **Local tests:** not run by the implementer. A local clone attempt failed because this environment could not resolve github.com; no local test result is claimed.
- **GitHub Actions:** run [41789549445](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41789549445) passed on code commit `b84aabe`: **150 tests passed** on each of Python 3.10, 3.11 and 3.12, including compileall.
- **Real Gemini persona transcript and device checks:** not run. The new script is provided for the owner to run.
- **Scope exclusions:** no changes to `web/`, `baymax/detection.py` detection patterns, emergency/safety reply text, shutdown ritual behavior, or `baymax/llm/gemini.py`. Branch `work/v0.7.0-session-memory` was not modified.

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


### Daily message-limit wording regression

- Added a service-level assertion for the rewritten daily-limit reply so the fixed-string contraction cleanup is covered end to end.
- **Verification:** test added; not run locally.


### Medical retry instruction refinement after Actions feedback

- The first Actions run reached 137 tests but failed only because the regression expected the exact wording "do not assume", while the retry prompt said "or assume". Made the retry instruction explicit ("Do not assume...") to align with the persona rule and test.
- **Verification:** the prior run had 1 assertion failure in the medical style-guard test on Python 3.10, 3.11 and 3.12. After making the retry instruction explicit, Actions passed on `7704b627def11b4829cf7d7f60311b28f8bde532`: 138 tests passed on each of Python 3.10, 3.11 and 3.12.


### Final implementation verification — 2026-11-04

- GitHub Actions run [41784781916](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41784781916) completed successfully on implementation commit `7704b627def11b4829cf7d7f60311b28f8bde532`.
- Test result: **138 passed** on Python 3.10, **138 passed** on Python 3.11, and **138 passed** on Python 3.12.
- Local unittest execution by the implementer: **not run**.
- Real Gemini and device checks: **not run**. Package version is now 0.6.6.


## v0.6.6 — persona and memory-gate fixes

- Set `baymax.__version__` to `0.6.6` after the owner confirmed the Actions result and authorized the version bump.
- **Verification:** Actions green on `d715fc5` (138 passed on Python 3.10, 3.11 and 3.12); local unittest **not run**; real Gemini and device checks **not run**.


## v0.6.7 — Task 1: exact persona rewrite

- Replaced the complete `PERSONALITY` string with the owner-supplied text, preserving `GUIDANCE`, `PERSONA = PERSONALITY + "\\n" + GUIDANCE`, and `RESPONSE_SCHEMA`.
- Checked the existing tests for assertions against old persona wording; none were found. Added structural prompt tests without asserting exact model replies.
- **Done-definition:** persona wording is final only when `tools/persona_check.py` reports zero flagged replies and the owner has read the transcript once. After that, persona changes require evidence from that script.
- **Verification:** tests added; local test execution and Actions have not yet been run on this branch.


## v0.6.7 — Task 2: style guard additions

- Preserved the single retry and prior style guards. Expanded the invented-technical-self-talk pattern to include `software`, `program`, `programmed`, `model`, `construct`, `designed`, `designed to`, `as designed` and `functioning`, alongside the existing body/mechanical terms.
- Added retry guards for `unable to tell` and `stop talking`. The fixed fallback phrase `lost my train of thought` was not added to a guard.
- Added pure pattern checks proving `I am an AI companion` is not flagged and the fixed fallback is not matched, plus FakeLLM retry tests for the two new guard cases.
- **Verification:** tests added; local test execution and Actions have not yet been run on this branch.


### Task 2 guard wiring correction

- Final source review found the two new patterns had been declared but were not yet included in the retry decision. Wired both into the existing one-retry violation expression and expanded the retry instruction to cover the full technical-word guard.
- **Verification:** source correction committed; tests not run locally; Actions not yet run.


## v0.6.7 — Task 3: persona check script

- Added `tools/persona_check.py` with Gemini as the default and a FakeLLM dry-run option. It reads settings through `Settings.from_env()`, uses a temporary database directory, isolates each group under a fresh user id, enables debug traces, waits one second between calls, and records per-message failures without exception text.
- Added the pure `flag_reply(user_text, reply, kind)` checker for the requested ten flags and the required kind exclusions. The report contains all five groups, reply kinds, trace warnings, and the requested summary/flagged-reply list; the same summary is printed to the terminal.
- Added table-driven positive/negative flag tests and a FakeLLM dry-run test for the full five-group report. Added the owner instructions to `docs/MANUAL_TEST.md`.
- **Verification:** tests added; local test execution and Actions have not yet been run on this branch. Real Gemini is not run by this implementation.


### Task 3 test-fixture correction

- Corrected the fallback flag's table-driven positive/negative fixture so the positive case is the exact brain fallback text and the negative case is a different, non-exact phrase.
- Clarified the silent shell-key entry command in the manual test instructions.
- **Verification:** fixture/doc correction committed; local tests not run; Actions not yet run.


## v0.6.7 — Task 4: CLI trace display

- Added the optional `readline` import with an `ImportError` fallback.
- The CLI now prints a response's non-empty `trace` immediately after its reply.
- Added a CLI test proving trace output follows the reply.
- **Verification:** test added; local test execution and Actions have not yet been run on this branch.


### Task 4 CLI trace insertion correction

- Final source review found the optional readline import was present but the trace-print insertion had not matched the original line. Added the trace output immediately after the reply.
- **Verification:** correction committed; local tests not run; Actions not yet run.


### Task 3 trace availability constraint

- Group E uses the existing shutdown ritual. ChatService does not provide a trace for ritual replies, even with debug enabled.
- Adding trace metadata to those responses would modify the explicitly protected shutdown-ritual path. The attempted service-side metadata change and its test have been reverted; the final diff leaves shutdown-ritual behavior and service code unchanged.
- The persona checker now states "Trace unavailable for this response kind" when the service does not supply a trace. It does not fabricate trace content.
- **Unresolved owner decision:** should the prohibition on touching the shutdown ritual remain absolute (accepting no trace for Group E), or may a debug-only trace field be added to ritual responses? No change will be made without clarification.
- **Verification:** regression updated; local tests not run; Actions pending on the resulting branch head.


### Task 3 Gemini initialization failure handling

- Deferred Gemini adapter-construction failures through a tiny failing adapter so the service can record a per-message error and continue the transcript, including when the key is absent or the SDK is unavailable. Exception text is not written; only the exception type reaches the transcript.
- **Verification:** code committed; local tests not run; Actions not yet run.


## v0.6.7 — Task 5: implementation log and release gate

- Recorded each task, its test additions, and follow-up corrections in the entries above.
- Confirmed the v0.6.7 branch is based on current main with no behind commits; the final compared file list contains only persona, brain, CLI, script, manual test, log and test files.
- **Release gate:** do not bump `baymax.__version__` until the owner confirms Actions is green on the final branch head. Persona wording is not final until the persona-check script reports zero flags and the owner has read the transcript once. Further persona edits after that require evidence from the script.
- **Verification:** local unittest **not run**; Actions run `41789549445` green on `b84aabe` (150 passed on each of Python 3.10, 3.11 and 3.12); real Gemini and device checks **not run**.


### Scope correction — keep shutdown ritual untouched

- Reverted all changes to `baymax/service.py` and `tests/test_service.py` that had been added solely to attach a debug trace to ritual responses. The final diff must not include service.py or change shutdown behavior.
- The script reports trace unavailability honestly for those responses; the requirement that every Group E response carry a trace remains blocked by the explicit no-shutdown-ritual-change rule and is raised for owner clarification.


### Scope cleanup follow-up

- Restored tests/test_service.py byte-for-byte to the main-branch version. The final change set contains no service.py or test_service.py changes; shutdown ritual code and its tests are untouched.
