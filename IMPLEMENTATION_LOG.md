# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-11-06

- **Repository:** `pijushpaul001/Tiny-Baymax`, branch `main`.
- **Package version:** `0.6.10`.
- **Tests:** GitHub Actions run 41826707933 passed 166 tests in each of six jobs (Python 3.10, 3.11, 3.12, each with a dummy `.env` and with no `.env` plus dummy shell variables); compileall passed. That run was before the version-only commit. Local unittest not run by the implementer.
- **Mode:** closed-friends mode (`BAYMAX_USER_CONTROLS=0`) is the intended deployment. Owner reads data with `tools/export_all.py`.
- **Models:** `BAYMAX_MODEL=gemma-4-26b-a4b-it`, `BAYMAX_FALLBACK_MODEL=gemini-3.5-flash-lite` (v0.6.9 example config).
- **Persona:** final unless `tools/persona_check.py` shows a problem.
- **Verified by the owner only, not by the implementer:** a first real Gemini call worked in Codespaces.
- **Not run:** phone/PWA check, HTTPS/Tailscale, microphone and speech, the full persona-check transcript review.
- **Next:** v0.6.11 face and voice in `web/`; docs-only cleanup PR; cloud VM with Tailscale; phone verification; UI polish.
- **Deferred (scope freeze):** reminders, tools, summaries, semantic memory, native push, iOS.

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
- **Trace behavior:** Group E has no trace by design because ritual replies never call the model. The checker reports trace unavailability for those replies; no ritual or service behavior is changed.
- **Verification:** regression updated; local tests not run; Actions run `41790022320` green on final code commit `4327baf` (149 passed on Python 3.10, 3.11 and 3.12).


### Task 3 Gemini initialization failure handling

- Deferred Gemini adapter-construction failures through a tiny failing adapter so the service can record a per-message error and continue the transcript, including when the key is absent or the SDK is unavailable. Exception text is not written; only the exception type reaches the transcript.
- **Verification:** code committed; local tests not run; Actions not yet run.


## v0.6.7 — Task 5: implementation log and release gate

- Recorded each task, its test additions, and follow-up corrections in the entries above.
- Confirmed the v0.6.7 branch is based on current main with no behind commits; the final compared file list contains only persona, brain, CLI, script, manual test, log and test files.
- **Release gate:** do not bump `baymax.__version__` until the owner confirms Actions is green on the final branch head. Persona wording is not final until the persona-check script reports zero flags and the owner has read the transcript once. Further persona edits after that require evidence from the script.
- **Verification:** local unittest **not run**; Actions run `41790022320` green on `4327baf` (149 passed on each of Python 3.10, 3.11 and 3.12); real Gemini and device checks **not run**.


### Scope correction — keep shutdown ritual untouched

- Reverted all changes to `baymax/service.py` and `tests/test_service.py` that had been added solely to attach a debug trace to ritual responses. The final diff must not include service.py or change shutdown behavior.
- The script reports trace unavailability honestly for those responses; the requirement that every Group E response carry a trace remains blocked by the explicit no-shutdown-ritual-change rule and is raised for owner clarification.


### Scope cleanup follow-up

- Restored tests/test_service.py byte-for-byte to the main-branch version. The final change set contains no service.py or test_service.py changes; shutdown ritual code and its tests are untouched.


### Final CI verification — 2026-11-04

- GitHub Actions run [41790139437](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41790139437) completed successfully on code commit `b88dccd2e61865a774c78ebcd0adfca4c24fba5c`.
- Result: **149 tests passed** on Python 3.10, **149 passed** on Python 3.11, and **149 passed** on Python 3.12. Compileall also passed in each job.
- Local unittest: **not run**. Real Gemini and device checks: **not run**.


## v0.6.7 — Task 6: configurable persona-check delay

- Added `--delay` to `tools/persona_check.py`, defaulting to 6.0 seconds; finite non-negative values are accepted and negative values are rejected. A value of 0 disables waiting.
- The delay is applied after model-backed replies only. Ritual, command and safety replies do not trigger a sleep.
- Updated the manual instructions and added argument-parsing tests for the default, a custom value, zero, and negative-value rejection.
- **Verification:** baseline Actions were green on `b88dccd` (149 passed on Python 3.10, 3.11 and 3.12). This delay change is verified only by the pull request's Actions run; local unittest not run; real Gemini and device checks not run.


## v0.6.7 — package version

- Bumped `baymax.__version__` to `0.6.7` in a separate commit after the persona-check delay change.
- **Verification:** Actions green on `b88dccd` (149 passed on Python 3.10, 3.11 and 3.12); the delay and version commits are verified only by the pull request's Actions run; local unittest not run; real Gemini and device checks not run. Group E has no trace by design because ritual replies never call the model.


## v0.6.8 — Task 1: structured persona examples and copied-example retry

- Moved the existing example exchanges into `EXAMPLES` tuples and generated the existing manner-example block from them. Exported `EXAMPLE_REPLIES`; changed only the instruction sentence before the examples as requested.
- Added normalized exact-reply detection to the existing model-reply violation check. It uses the existing single retry with the requested instruction; a second copied reply is accepted and deterministic Python replies never enter this check.
- Added FakeLLM tests for retry-and-rewrite, a non-example pass, acceptance of a copied reply on retry, and deterministic-reply exclusion. Added a prompt test that the rendered example block is generated from the tuple data.
- **Verification:** tests added; local unittest and Actions not yet run for this branch.


### Task 1 normalization-test correction

- Strengthened the copied-example FakeLLM case to vary capitalization and punctuation while preserving the normalized sentence, and corrected the generated-block assertion to join lines with actual newline characters.
- **Verification:** source/test correction committed; local unittest and Actions not run.


## v0.6.8 — Task 2: persona-check coverage and failure handling

- Added model, fallback-model and selected delay headers to the Markdown transcript; the API key is never included.
- Added Group F paraphrases after Group D. Each Group F prompt receives a unique user id. Added informational counting of replies identical to persona examples after case/punctuation/whitespace normalization.
- Added a missing-Gemini-key check before the script creates temporary data or starts model work, inserted the repository root into `sys.path`, and added one stderr progress line per message.
- Added model-call tracking so delay occurs only after an actual model attempt. After three consecutive LLM failures, the script stops, writes the partial transcript, and reports the stop reason without exception text.
- Added pure count tests and expanded the FakeLLM dry-run expectations for Group F and transcript headers.
- **Verification:** tests added; local unittest and Actions not yet run for this branch.


## v0.6.8 — Task 3: local environment and swap-file ignores

- Added ignore rules for `.env.*` and `*.swp`, followed immediately by `!.env.example` so the example configuration remains trackable.
- **Verification:** `git check-ignore -v` confirmed `.env`, `.env.local` and `editor.swp` are ignored; `git check-ignore .env.example` returned exit status 1 (not ignored). Check was run in a temporary local Git repository using the committed ignore rules. No unit test applies to this configuration-only change.


## v0.6.8 — Task 4: bypass retries for daily Gemini quota

- Added a narrow 429 check for provider exception text containing `PerDay` or `requests per day`, case-insensitively. A daily-quota response immediately advances to the configured fallback model, or raises when no fallback exists.
- Per-minute 429 handling retains the existing three-attempt backoff and fallback sequence. Provider exception text is used only for the daily-quota decision and is not logged or returned.
- Added fake-exception tests for daily quota with fallback, daily quota without fallback, and per-minute retry preservation.
- **Verification:** tests added; local unittest and Actions not yet run for this branch.


## v0.6.8 — Task 5: Gemini free-tier and privacy notes

- Added owner-specified comments to `.env.example` covering the stated per-model free-tier daily request limits, Gemma token-per-minute cap, and the free-tier content-use warning. The comments explicitly say quotas are small, model-specific and can change.
- Added the instruction to use the paid tier before sharing the app. No credentials or values were added.
- **Verification:** documentation-only change reviewed in the resulting file; local unittest not applicable and Actions not yet run.


## v0.6.8 — Task 6: explicit status wording in persona

- Added the requested sentence immediately after the technical-terms sentence in `WHAT BAYMAX IS`.
- Added a prompt-content assertion. Existing style-guard patterns and the one-retry limit were not changed for this item.
- **Verification:** test added and source diff reviewed; local unittest and Actions not yet run for this branch.


## v0.6.8 — package version

- Bumped `baymax.__version__` from `0.6.7` to `0.6.8` in this version-only code commit after Tasks 1–6 were committed.
- **Verification:** no Actions run was visible for the last commit before this bump (`699f997956f473132664e1c4234fd63f7e2a1db6)); PR Actions pending after PR creation; local unittest **not run** (clone failed because github.com could not be resolved); real Gemini and device checks **not run**.


### v0.6.8 Actions verification update

- The last commit before the version bump (`699f997956f473132664e1c4234fd63f7e2a1db6`) passed GitHub Actions run [41812930363](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41812930363): 162 tests passed on Python 3.10, 3.11 and 3.12; compileall passed in all jobs.
- PR #7 head `7a6c3c18a83de437f872c70119943999f05db1e3` passed GitHub Actions run [41813050593](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41813050593): 162 tests passed on Python 3.10, 3.11 and 3.12; compileall passed in all jobs.
- Local unittest remains **not run**. Real Gemini and device checks remain **not run**.


## v0.6.9 — Task 1: remove copied-example retry

- Removed exact persona-example matching from the model style-violation decision. All other style guards and the existing maximum of one retry remain unchanged; `EXAMPLE_REPLIES` remains exported by `baymax.persona`, and the persona-check count remains informational.
- Replaced the copied-example retry tests with a FakeLLM regression proving an example-identical reply is accepted after exactly one model call. Existing tests for all other style guards were retained.
- **Verification:** source and test edits committed; local unittest and GitHub Actions not yet run.


## v0.6.9 — Task 2: trim general-situation persona examples

- Removed only the seven requested user/reply examples from `EXAMPLES`; retained all other examples and the exported reply tuple.
- Replaced the instruction immediately before the examples block with the exact owner-provided sentence.
- Updated the generated-block assertion and added a regression asserting all seven removed user lines are absent from `PERSONA`.
- **Verification:** source and test edits committed; local unittest and GitHub Actions not yet run.


## v0.6.9 — Task 3: low-mood detection and dependency cue

- Extended only `EMOTION` with the requested feel/feeling + optional-intensifier low-mood phrases and "feel like crying". The low-on negative lookahead excludes "feeling low on ..."; emotional labels are reduced to the single mood word for rating grammar.
- Added the requested `down`, `low`, `blue` and `empty` adjective mappings. The generated question for "I have been feeling really down" is asserted exactly.
- Added positive emotional/rating tests for all six required phrases and negative controls for all five non-emotional uses. Added "do not leave me" to `DEPENDENCY_CUE` and a regression for reassurance mode plus trusted-person instruction.
- `URGENT`, `SELF_HARM`, both safety reply strings, and unrelated existing detection tests were not edited.
- **Verification:** source and test edits committed; local unittest and GitHub Actions not yet run.


## v0.6.9 — Task 4: recommended Gemini setup documentation

- Set the example configuration to `BAYMAX_MODEL=gemma-4-26b-a4b-it` and `BAYMAX_FALLBACK_MODEL=gemini-3.5-flash-lite`.
- Documented the owner-provided timing, free daily quota and 16K tokens-per-minute information for the recommended model, and the approximately 27-second tiny-prompt measurement for `gemma-4-31b-it` as too slow for chat.
- Preserved the warning that Google may use free-tier content to improve its products and the instruction to use the paid tier before sharing.
- **Verification:** documentation and example configuration edits committed; no external model-performance measurements were run by the implementer.


## v0.6.9 — Task 5: extend persona-check Group F

- Added exactly the three requested prompts to Group F: "I feel really low", "I am feeling blue" and "do not leave me". No other persona-check behavior or group content was changed.
- Updated the dry-run transcript test to assert those prompts are present and the expected total message count is 49.
- **Verification:** script and test edits committed; local unittest and GitHub Actions not yet run.


## v0.6.9 — package version

- Bumped `baymax.__version__` from `0.6.8` to `0.6.9` in a separate version commit after Tasks 1–5 were committed.
- **Verification at the pre-bump implementation head `6b9eefd6b53455c292850698e85c0cc07b810a7e`:** no GitHub Actions runs or combined status checks were visible through the repository status endpoints. Local unittest **not run**. Real Gemini and device checks **not run**. PR Actions status will be checked after PR creation.


### v0.6.9 Actions correction — persona example count fixture

- The first PR Actions run found one stale test fixture: the informational example-count test hard-coded the greeting reply that Task 2 intentionally removed from `EXAMPLES`. Updated the fixture to derive its case/punctuation/whitespace variant from the current first `EXAMPLE_REPLIES` entry. No production behavior changed.
- **Verification:** GitHub Actions run [41822457289](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41822457289) showed this single assertion failure (165 tests ran) on Python 3.12 and 3.11; Python 3.10 was still in progress when inspected. The correction is committed; rerun status pending. Local unittest **not run**.


### v0.6.9 Actions verification after fixture correction

- GitHub Actions run [41822622967](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41822622967) completed successfully on code/test head `1b6de5342dd9bf98d152d833d90b0225090a757e`.
- Result: **165 tests passed** on Python 3.10, **165 passed** on Python 3.11, and **165 passed** on Python 3.12. Compile steps also passed in all three jobs.
- Local unittest: **not run**. Real Gemini and device checks: **not run**.


## v0.6.10 — test environment isolation

- Audited all test files for `Settings.from_env()`, `load_dotenv()`, `GEMINI_API_KEY`, `BAYMAX_*` and persona-check key-validation usage. The unisolated path was `tests/test_persona_check.py::PersonaCheckDryRunTests.test_fake_main_writes_all_groups_and_prints_summary`: it calls `tools.persona_check.main()`, which calls `Settings.from_env()` and then `load_dotenv()`. The CLI test already patches `Settings.from_env()`. No test directly calls `load_dotenv()`; the persona-check fake-main test reaches it indirectly. Added explicit coverage for the Gemini missing-key check, which also calls `Settings.from_env()`.
- Added a test helper that removes all `BAYMAX_*` and `GEMINI_API_KEY` shell variables for the duration of the test and changes into a temporary working directory with no developer `.env`. Applied it to the persona-check fake run and missing-key test. No application code or runtime configuration behavior changed.
- Expanded the Actions matrix to run the entire suite in two separate modes: (1) a dummy-key `.env` with no Gemini/Baymax shell variables, and (2) no `.env` with dummy `GEMINI_API_KEY` and `BAYMAX_*` shell variables. This ensures each configuration source is exercised independently.
- **Verification:** GitHub Actions run [41826707933](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41826707933) passed all six matrix jobs: Python 3.10, 3.11 and 3.12 with the dummy `.env`, and all three versions with no `.env` plus dummy shell variables. Each job ran **166 tests successfully** and passed compileall. Local unittest **not run**; a local clone attempt failed because this environment could not resolve `github.com`.


## v0.6.10 — package version

- Bumped `baymax.__version__` from `0.6.9` to `0.6.10` in the dedicated version-only commit `174e9bd38752bf4d4e98e40bc63f55440d50f934`.
- **Verification before version bump:** Actions run [41826707933](https://github.com/pijushpaul001/Tiny-Baymax/actions/runs/41826707933) passed 166 tests in each of six combinations (Python 3.10/3.11/3.12 × dummy `.env`/no `.env` with dummy shell variables); compileall passed in all jobs. Local unittest **not run**. The version-only commit and following log commit require their own Actions result; real Gemini and device checks **not run**.


## v0.6.11 — face logic

- Added the pure `faceParams(emotion, reducedMotion)` calculation with baseline defaults, finite-number handling, the specified scaling/interval formulas and clamps.
- Added a small browser controller for emotion-driven eye scaling, jittered blinking, hidden-tab pause and reduced-motion support. CSS custom properties are applied with `style.setProperty`.
- Added Node-backed tests for baseline values, concern, happiness, clamps, malformed input and reduced motion.
- **Verification:** `python -m unittest tests.test_face_logic -v` passed locally (1 test; Node.js v22.16.0). Browser rendering and phone behaviour not tested. This commit contains face logic only; chat-panel integration follows separately.


## v0.6.11 — face panel integration

- Added the inline SVG face above the conversation heading, with a white body, pale grey outline, two black ellipse eyes and a thin joining line. No mouth or extra features were added; `baymax.svg` is unchanged.
- Added CSP-compatible CSS for smooth eye-size changes and blink styling. The controller applies CSS custom properties through `style.setProperty`.
- Connected the face to `session.emotion` on connect and to `result.emotion` when present after chat and ritual responses. Missing emotion keys are guarded.
- Added integration checks for the face element, script reference, emotion updates, and the no-inline-script/no-style-attribute rules.
- **Verification:** locally ran `python -m unittest tests.test_face_logic tests.test_web_integration -v` in the face-only working copy: 9 tests passed. Node.js v22.16.0 was available. Phone rendering and real reduced-motion behaviour remain unverified.


## v0.6.11 — speech synthesis and voice preference

- Added `pickVoice(voices, lang)`: exact locale first, then English, preferring local-service voices within the selected group. No voice names are hard-coded.
- Added the top-bar Voice on/off control (default on), with its preference stored client-side under the single key `tiny-baymax-speak`. Storage access is wrapped in `try/catch`; the passcode and token are not stored.
- Live chat and safety replies plus the shutdown ritual prompt are spoken at rate 0.85 and pitch 0.9. History rendering does not call speech. Speech is cancelled on user send, Voice off and session end. The `voiceschanged` event refreshes voice selection. The control is hidden when speech synthesis is unavailable.
- Added Node voice-selection cases and web integration assertions for live-only speech, rate/pitch and storage boundaries.
- **Verification:** local face/voice and web integration tests passed in the combined working copy (10 tests). Node.js v22.16.0 was available. Actual device voices, audio quality and browser support are unverified.


## v0.6.11 — optional microphone input

- Added an optional composer microphone button using `SpeechRecognition` or `webkitSpeechRecognition`, with `navigator.language` as its locale.
- Recognition fills the message textarea and does not submit it. Starting to listen cancels speech synthesis; sending a message stops recognition. Unsupported browsers hide the microphone control.
- Added a short permission-denied state and a generic unavailable state.
- Added integration checks for support detection, locale, textarea fill, no auto-send and the permission message.
- **Verification:** local `python -m unittest tests.test_face_logic tests.test_web_integration -v` passed in the combined working copy (10 tests). Browser microphone permission and phone behaviour remain unverified.


## v0.6.11 — static asset cache and JavaScript CI checks

- Added `/face.js` and `/speech.js` to the service-worker static asset list and changed the cache name to `tiny-baymax-static-v2`.
- Added a CI step that runs `node --check` for every `web/*.js` file.
- Added an integration check for the cache version and both new assets.
- **Verification:** local web integration suite passed in the combined working copy (11 tests); JavaScript syntax checks passed locally with Node.js v22.16.0. GitHub Actions has not yet run on this branch.


## v0.6.11 — manual phone checklist

- Added Section H with the requested face, emotion reaction, Voice toggle, speech quality, microphone, reduced-motion and cancel-on-send checks.
- All checks remain unchecked; no phone/device behaviour is claimed as verified.
- **Verification:** documentation reviewed; no manual phone checks were performed.


### v0.6.11 local validation — current branch implementation

- Ran `python -m unittest discover -s tests -t . -v`: **172 tests passed**.
- Ran `node --check` for every `web/*.js` file: passed (Node.js v22.16.0).
- Ran `python -m compileall -q baymax server tests`: passed.
- GitHub Actions has **not** been reported green by the owner; no CI success is claimed here. Phone checks in Section H remain unchecked.
- No files under `baymax/` or `server/` were changed. Package version remains 0.6.10. No PR was opened.


### Speech scope guard correction

- Restricted spoken chat responses to the specified live kinds only: `chat`, `safety` and `ritual`. Command, limit and error replies are not spoken. Session-end cancellation remains in place.
- Added an integration assertion for the allowed response kinds.
- **Verification:** the focused voice integration test passed locally; `node --check web/app.js` passed. Full suite rerun follows this correction.


### v0.6.11 post-correction verification

- After restricting speech to `chat`, `safety` and `ritual` response kinds, reran `python -m unittest discover -s tests -t . -v`: **172 tests passed**.
- Re-ran `node --check` for every `web/*.js` file: passed (Node.js v22.16.0).
- Re-ran `python -m compileall -q baymax server tests`: passed.
- GitHub Actions and phone checks remain pending/unverified.


### Storage assertion strengthening

- Tightened the web integration test to assert that the only two localStorage calls are the read and write of `SPEAK_PREFERENCE_KEY`, which resolves to `tiny-baymax-speak`. The existing explicit token/passcode write checks remain.
- **Verification:** focused closed-friends web integration test passed locally. Full suite rerun follows this test-only correction.


### v0.6.11 final local verification after storage-test strengthening

- Ran `python -m unittest discover -s tests -t . -v`: **172 tests passed**.
- Ran `node --check` for every `web/*.js` file: passed (Node.js v22.16.0).
- Ran `python -m compileall -q baymax server tests`: passed.
- Actions remains pending owner confirmation; phone checks remain unchecked.


## v0.6.11 follow-up — keep the face visible during message scrolling

- **Cause:** the conversation panel used a minimum height rather than a constrained height, while the messages list also had a viewport-based maximum height and a 260px minimum. The combined content could exceed the panel, so the page/panel scrolled instead of keeping the face and composer in a fixed conversation frame.
- Moved the face to immediately after the conversation heading and directly before `#messages`; it remains outside the message list.
- Constrained the conversation panel height at desktop and narrow widths. The messages list now owns the flexible remaining height and is the only scrolling conversation region. The face is non-shrinking and 84px wide; composer and interaction tools remain outside the scrolling list.
- Added a structural integration test proving the face precedes `#messages` and is not inside its contents.
- **Verification:** tests added; not run locally in this GitHub-only editing session. GitHub Actions is ready to validate this commit. No phone/browser visual test is claimed.


## v0.6.11 follow-up — remove permanent chat-screen lines (owner decision)

- **Owner decision, 2026-11-06:** deliberately removed the always-visible emergency line and the "not a doctor or emergency service" line from the chat screen. This is an explicit owner decision, not an implementation reinterpretation.
- Removed both paragraphs from `web/index.html`, the JavaScript write to `#emergency-line`, and the now-unused `.disclaimer` CSS. The connect-screen privacy note remains.
- Kept `#offline-card`, its dynamic emergency-hint text and failed-send visibility behaviour, its position before `#connect-screen`, and all deterministic emergency replies unchanged.
- Updated integration assertions to require the two strings to be absent while verifying the offline card is retained and displayed in the shared send-error catch path for 401, 429 and network failures.
- Updated README, architecture and manual-test wording to state that the app keeps the offline emergency card only. Added the face-scroll visibility manual check. Appended the owner's superseding decision verbatim to the end of the Architecture change history.
- **Verification:** tests updated; not run locally in this GitHub-only editing session. GitHub Actions is ready to validate this commit. No deterministic safety reply or Python/server file was changed.


### Face/composer flex sizing follow-up

- Explicitly made the conversation heading, interaction tools, composer and speech-error row non-shrinking flex items. The messages list alone takes the remaining panel height and scrolls.
- Extended the structural integration test to assert the message scroll container and non-shrinking composer/tool regions.
- **Verification:** regression assertions added; not run locally in this GitHub-only editing session. Actions should validate this follow-up commit.


### Manual checklist wording clarification

- Reworded the manual check to describe the absence of permanent chat-screen emergency/disclaimer copy without retaining the superseded line labels. The check still confirms the offline emergency card and connect-screen privacy note.
- **Verification:** documentation-only wording update; no tests run for this commit.


## v0.6.11 follow-up — retune visible emotion response

- **Cause 1 confirmed:** the previous face formula used a 0.90 concern span and a 0.15 concern coefficient. At concern 0.35 it produced eyeScale approximately 1.042, a roughly 4% increase. Replaced it with the owner-specified 0.50 concern span and 0.25 coefficient; concern 0.35 now produces 1.125.
- **Cause 2 verification, point 1 — response wiring:** connect calls `updateFace(session.emotion)`. Every normal chat response is built by `ChatService._resp` with the current emotion; the browser checks for the emotion field and calls `updateFace(result.emotion)`. The end-session response also updates the face when emotion is present. This wiring was already present.
- **Cause 2 verification, point 2 — CSS scale application:** `updateFace` writes `--eye-scale` through `style.setProperty`. The eye rule consumes it in `transform: scale(var(--eye-scale, 1))` and already had `transform-box: fill-box` plus `transform-origin: center`. The scale application path was present; the transition was retuned separately.
- **Cause 2 verification, point 3 — blink composition:** the blinking selector includes the same `scale(var(--eye-scale, 1))` before `scaleY(.06)`; blinking therefore preserves the emotion scale rather than replacing it. No extra face behaviour or mouth was added.
- **Cause 2 verification, point 4 — transition:** the previous eye transform transition was 480 ms, below the requested 800–1,000 ms. Changed the normal eye transform transition to 900 ms. The blink state retains its short blink-duration override for the blink itself.
- Retuned `faceParams` to the requested concern/happiness excess calculations, coefficients and clamps. Baseline remains exactly `eyeScale=1.0`, `blinkIntervalMs=5000`, `blinkDurationMs=160`; missing, non-numeric and non-finite emotion values use baseline defaults; reduced motion still disables blinking.
- Updated Node-backed formula tests for concern 0.35, concern 0.60+, happiness 0.70, extreme values, invalid/non-finite inputs and reduced motion.
- Added a FakeLLM-backed service integration test proving the `my head hurts` response exposes concern >= 0.30. The immediate pain-rating path is deterministic and intentionally does not invoke FakeLLM; the test asserts that no model call occurs.
- Added a structural web integration test proving the chat response emotion is passed to `updateFace`, and CSS assertions for centered SVG scaling, the 900 ms transition and scale-preserving blink rule.
- Updated Manual Test Section H with the requested phone checks for visible eye growth after `my head hurts` and slight eye reduction after `I got the job!`.
- **Verification:** source and test changes committed; local test suite not run in this GitHub-only editing session. GitHub Actions will validate this commit. Actual phone rendering remains unverified; leave Section H unchecked until tested. No files under `baymax/` or `server/` were changed. Package version remains 0.6.10. No PR opened.


## v0.6.11 follow-up — adorable face and two-axis expression (owner decision 2026-11-06)

- **Owner decision, 2026-11-06:** deliberately revise the earlier face design: the face should be cuter and more adorable, not movie-accurate. The on-screen face area remains unchanged; only facial elements are enlarged. This supersedes the earlier small, movie-style eye treatment in CLAUDE_HANDOFF.md H-2.
- Kept the white body and pale grey outline, slightly rounded the body further, and increased the two baseline eye ovals by 50% (rx 4.2→6.3; ry 5.2→7.8). Their positions preserve a clear margin to the body edge and a visible central joining line.
- Added exactly one small white highlight dot in the upper part of each eye group. No mouth, extra facial feature, new colour, or additional animation was added.
- Replaced the single `eyeScale` result with `eyeScaleX` and `eyeScaleY` using the owner's exact concern/happiness excess formulas and clamps. Baseline remains exactly X=1, Y=1, blink interval 5000 ms, blink duration 160 ms. Missing, non-numeric and non-finite fields continue to use baseline values.
- Preserved blink interval, duration and reduced-motion logic from the previous tuning. Moved blink class application to the two parent `.face-eye-blink` groups while expression transforms apply to each child `.face-eye` group; this composes the vertical blink with the X/Y expression scaling. The eye transform uses `--eye-scale-x` and `--eye-scale-y`, centered with `transform-box: fill-box` and `transform-origin: center`, and retains the 900 ms transition.
- Updated Node-backed face-parameter tests for concern 0.35, concern 0.60+, happiness 0.70, happiness 0.80+, baseline, malformed/non-finite input and reduced motion. Updated web structural/CSS assertions and added a structural SVG test for exactly two eye groups, exactly one highlight per eye, and no mouth/path/text element.
- Updated Section H of `docs/MANUAL_TEST.md` to check that eyes visibly get taller after `my head hurts` and visibly flatter after `I got the job!`.
- **Verification:** source, tests and docs committed; local tests not run in this GitHub-only editing session. GitHub Actions is ready to validate this commit. Actual phone rendering remains unverified; manual Section H items remain unchecked. No files under `baymax/` or `server/` were changed. Package version remains 0.6.10. No PR opened.


### Face blink transition and SVG structure test correction

- Follow-up source review found the parent blink group had its transition declared only while the blink class was active. Moved the transition declaration to the base parent-group rule so both closing and reopening use the configured blink duration; the active class now changes only its vertical scale.
- Tightened the SVG structure test to verify each highlight is nested inside its own eye group, and corrected the no-mouth/no-extra-SVG-element assertion to use actual regex word boundaries.
- **Verification:** correction committed; local tests not run in this GitHub-only editing session. Actions will validate the updated branch head. No additional runtime behaviour or files under `baymax/` or `server/` changed.


## v0.6.12 chibi figure — owner decision 2026-11-10

- Replaced the face-only SVG in `web/index.html` with the specified full-body chibi figure: cream rounded head and pear-shaped torso, two plain black oval eyes joined by a thin bridge, arms, hands, legs, and grey armour plates. The SVG keeps `id="baymax-face"`, remains inside `.baymax-face-area` before `#messages`, contains no mouth/highlights/extra elements, and preserves the exact requested draw order.
- Updated `web/styles.css` with the cream/brown figure palette, grey plates, 72×120 desktop SVG sizing and 58×97 mobile sizing. Preserved the existing eye blink/scale rules, 900 ms eye transition, reduced-motion blink handling, face-area layout, messages scrolling and composer layout.
- Updated `tests/test_web_integration.py` to require two plain eye groups and blink groups, no highlights/circles/mouth/path/text, one bridge line, figure-part/plate classes, and the new sizing rules. Retained the existing face placement and scroll/composer assertions.
- Updated `CLAUDE_HANDOFF.md` by appending the requested 2026-11-10 owner-decision line to Architecture change history; no earlier architecture text was edited. Added the two requested unchecked phone checks to Section H of `docs/MANUAL_TEST.md`.
- **Files changed:** `web/index.html`, `web/styles.css`, `tests/test_web_integration.py`, `CLAUDE_HANDOFF.md`, `docs/MANUAL_TEST.md`, `IMPLEMENTATION_LOG.md`.
- **Not done:** no changes to `web/face.js`, `web/app.js`, `web/speech.js`, `web/sw.js`, `baymax/`, `server/`, `tools/`, shutdown ritual, safety code, or package version. No PR opened. No phone/browser rendering performed.
- **Version gate:** inspected `baymax/__init__.py`; the current package version on this branch (inherited from `main`) is `0.6.11`. The expected next patch version `0.6.12` is therefore consistent, but was deliberately not changed before owner confirmation that Actions is green.
- **Verification status:** this session has GitHub connector access but no working network route to clone the current repository locally. The only available repository ZIP is dated 2026-11-04 and is not the current `main` baseline, so running the requested full suite against it would not verify this branch. Consequently `node --check web/*.js`, `python -m compileall -q baymax server tests tools`, and `python -m unittest discover -s tests -t . -v` were not run locally; Python 3.10/3.11/3.12 matrix results are also pending GitHub Actions. Phone rendering is unverified. Do not treat CI as green until Actions reports success on this branch HEAD.
- **Specification note:** no ambiguity requiring an implementation guess was found. The specified SVG's torso and head are ellipses rather than a mathematically pear-shaped path; the supplied SVG was followed exactly as requested.


## v0.6.12 chibi figure redraw — owner-supplied SVG, 2026-11-10

- Replaced the earlier hand-written figure SVG in `web/index.html` with the owner's supplied redraw verbatim, preserving every path, coordinate, SVG presentation attribute, element order and comment. Kept `id="baymax-face"`, the existing `.baymax-face-area` wrapper, and placement before/outside `#messages`.
- Replaced the specified figure CSS rules in `web/styles.css` with the exact owner-supplied values: 80×133 desktop, 64×107 mobile, cream body/parts, grey plates, round joins/caps, chest line and 1.8px eye bridge. Existing blink, eye scaling/900ms transition, and face-area rules were left unchanged. Message, conversation-panel and composer rules were not changed.
- Updated `tests/test_web_integration.py`: exactly two eye groups and blink groups; zero highlights/circles; exactly two ellipses (eyes); each eye group contains only one ellipse; one bridge; one head path; figure part/plate presence; forbidden-element regex now bans mouth and text but allows paths. Updated the desktop sizing assertion; other existing assertions retained.
- Appended the requested redraw decision verbatim to the end of Architecture change history in `CLAUDE_HANDOFF.md`; retained all earlier text. Kept the two previous unchecked figure checks in Section H and added the eye-growth check.
- **Files changed:** `web/index.html`, `web/styles.css`, `tests/test_web_integration.py`, `CLAUDE_HANDOFF.md`, `docs/MANUAL_TEST.md`, `IMPLEMENTATION_LOG.md`.
- **Not done:** no changes to `baymax/`, `server/`, `tools/`, `web/face.js`, `web/app.js`, `web/speech.js`, `web/sw.js`, shutdown ritual or safety code. No version bump, PR or merge. No phone/browser rendering.
- **Verification:** GitHub source edits and branch diff were inspected. This session cannot run shell commands against the current branch checkout, so `node --check web/*.js`, `python -m compileall -q baymax server tests tools`, and `python -m unittest discover -s tests -t . -v` were not run locally. The test count and Python 3.10/3.11/3.12 results remain unverified pending Actions. Do not claim CI success; wait for the branch-head Actions result.
- **Spec review:** no coordinate or design ambiguity was found; the supplied SVG and CSS were applied as written. The SVG uses multiple subpaths inside the hand paths, which is valid and intentional; tests permit path elements while still rejecting mouth and text elements.


## v0.6.12 figure CSS refinement — owner confirmation, 2026-11-10

- Applied the owner's supplied figure CSS formatting and declarations in `web/styles.css`: explicit multiline figure/body/plate/line/bridge rules, black eye fill with no stroke, and centered fill-box transforms for the eye and blink groups.
- Preserved the existing expression-driven X/Y eye scaling and 900 ms transition, plus the parent-group blink transition and blink scale. Kept the existing desktop (80×133) and mobile (64×107) SVG dimensions and all surrounding layout rules.
- Updated `tests/test_web_integration.py` to assert the no-stroke eye styling and preserved configurable blink transition.
- **Files changed:** `web/styles.css`, `tests/test_web_integration.py`, `IMPLEMENTATION_LOG.md`.
- **Verification:** GitHub source updates only; local tests and browser/phone rendering were not run. GitHub Actions status must be checked on the resulting branch HEAD. No changes to `baymax/`, `server/`, other web JavaScript, version, PR or merge.
