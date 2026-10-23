# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Implementation snapshot:** v0.6.1 hardening candidate
- **Architecture:** Claude's detailed v0.6 architecture reviewed; use it as the contract for follow-up work.
- **Automated verification:** GitHub Actions passed all 84 tests on commit `7ace26bb7ec8567e5e89f69d2919ce5dcf56a891` on Python 3.10, 3.11, and 3.12. This is the latest verified code/test commit before this log-only update.
- **GitHub sync:** Source is being committed to `work/v0.6.1-hardening`. `main` remains documentation-only until the pull request is reviewed and merged.
- **Real Gemini / device verification:** Not run. These require the user's configured API key and phone/network environment.
- **Last updated:** 2026-10-23

## Summary

| ID | Area | Status | Details |
|---|---|---|---|
| SETUP-001 | Repository coordination files | Done | `README.md`, `CLAUDE_HANDOFF.md`, `AGENTS.md` retained; this implementation log updated. |
| PHASE0-001 | Project hygiene and tests | Done in this snapshot | Added `.github/workflows/tests.yml`, expanded `.gitignore`, regression tests, and `docs/MANUAL_TEST.md`. The source bundle did not contain the original `tests/` or `web/` directories, so these test files and web client are new additions rather than restored originals. |
| G3 | Shutdown answer classification | Done | Negative phrases are evaluated before positives, avoiding `very disappointed` or `not satisfied` being treated as satisfied. |
| G5 | Feedback secret redaction | Done | Shutdown feedback is redacted before persistence. |
| G2, G10 | Rating persistence and atomic writes | Done | Turn messages, emotion, rating event, memory and usage save atomically via `Store.persist_turn`. A rating survives an LLM failure. |
| G12, G15 | Safety-first response path | Done | Emergency/self-harm patterns are checked before storage reads/model calls and return deterministic guidance with a not-medical-advice statement. |
| G1, G13 | Rating capture | Done | Handles numbers/words, skip, corrections, ambiguous answers, and incidental-number avoidance. |
| G14 | Rating management | Done | Per-item rating edit/delete API routes. |
| G4 | Exit intent | Done | Short whole-message exit phrases are recognized without broad matches like “I am done with my project.” |
| G7 | HTTP error handling | Done | Invalid content length, oversized requests, SQLite failures, and unexpected exceptions receive JSON error responses. |
| G6 | Digit-group redaction | Done | Redaction recognizes 12–19 digit sequences with spaces/dashes; 10-digit phone-like values are not redacted on length alone. |
| G8 | CORS / OPTIONS | Done | Explicit origin allowlist and OPTIONS support; the default allowlist is empty. |
| G9 | Failed login throttling | Done | Per-client temporary lockout after repeated invalid passcodes. |
| G11 | SQLite schema versioning | Done | Uses `PRAGMA user_version`, a transactional baseline migration, and pre-migration backups. |
| G17 | User deletion encapsulation | Done | Added `ChatService.forget_user`; API no longer directly mutates private session state. |
| UI-001 | Web client | Implemented; browser review pending | Newly created responsive browser/PWA client with rating chips, satisfaction quick replies, memory/rating controls, export/delete-all, consent gate, and offline banner. `web/` was missing from the source ZIP. |
| VERIFY-001 | Real-world verification | Not started | Requires a real Gemini request and user's phone/browser/HTTPS route. See `docs/MANUAL_TEST.md`. |
| MOBILE-001 | Native mobile shell | Later phase | Capacitor/Android shell remains outside this hardening snapshot. |
| REMIND-001 | Reminders | Later phase | v0.7.0 reminder work remains out of scope. |

## Validation run (2026-10-13)

- `python -m compileall -q baymax server tests` — **passed**.
- `python -m unittest discover -s tests -t . -v` — **41 tests passed**.
- `node --check web/app.js` — **passed**.
- `node --check web/sw.js` — **passed**.
- HTTP smoke tests with `FakeLLM` verify static assets, public health endpoint, session greeting, immediate rating prompt, ratings retrieval and satisfaction-before-close flow.
- One `[error] API request failed: RuntimeError` line is expected: the test intentionally raises an exception to verify the JSON 500 response.

## Known limitations and risks

1. The input ZIP supplied core v0.6.0 modules and docs, but no original `tests/` or `web/`. The included tests and web app are new architecture-guided additions and need visual/browser testing.
2. No actual Gemini request was made; current model identifier availability, quota behavior, structured output and real reply quality remain unverified.
3. No phone, HTTPS tunnel, Tailscale route, PWA installation, speech or native Android build was tested.
4. Session-only state (active rating wait, shutdown ritual and safety hold) remains in process memory and resets after server restart, as documented in the architecture.
5. Consent is enforced in the web UI. This does not establish legal or regulatory compliance.
6. Source is being committed to a work branch. Do not mark `main` or a deployment as implemented until review/merge and manual verification are complete.

## Next steps

1. Verify GitHub Actions and the full test matrix after R2-1 through R2-7; address any failures before further review.
2. Review the draft pull request against G1–G18 and AC-1–AC-16 in `CLAUDE_HANDOFF.md`; handle remaining findings in separate commits.
3. Run `docs/MANUAL_TEST.md` with the fake model, then real Gemini, then the user's phone.
4. Record only verified outcomes. Do not move to the native mobile shell until Phase 1 tests pass and Phase 2 results are recorded.

## Entry template

### YYYY-MM-DD — ID — Short title

- **Status:** Done / In progress / Blocked
- **Architecture requirement:** Link the applicable section in `CLAUDE_HANDOFF.md`
- **Files changed:**
- **Implementation notes:**
- **Tests run and results:**
- **Known limitations / risks:**
- **Next step:**

## Claude review follow-up — 2026-10-15

Review source: user-provided Claude review of PR #1 at commit `b18e7b6`. The review reported 41 tests passing in its sandbox, but did not verify live Gemini, browser rendering, phone/PWA installation, HTTPS/proxy deployment, or GitHub Actions. Those are not recorded as completed here.

### Implemented on `work/v0.6.1-hardening`

- **F1 / AC-6:** Satisfaction answers now require a complete short reply. Longer replies such as “yes, but my head hurts really bad” return to normal intent detection instead of ending the session. Added regression tests, including “no problem, I am satisfied.”
- **F2 / AC-9:** Added direct service methods for remembering a fact, clearing history, and resetting simulated emotion. API controls no longer pass these actions through the active shutdown dialogue state. Added API regression tests.
- **F5 / AC-4:** Expanded rating parsing for common phrasing, worded “seven out of ten,” “skip it,” and “I’d rather skip,” while retaining negative tests for incidental numbers.
- **F4 / G9:** Added opt-in `BAYMAX_TRUSTED_PROXY=1`. A forwarded address is used only when explicitly enabled, the direct peer is loopback, and the forwarded value parses as an IP address. The default remains off. Added focused resolver tests and setup documentation.

### Deferred or still open

- **F3 / AC-7:** Implemented best-effort post-response persistence. The deterministic safety reply is constructed before persistence and returned unchanged even if persistence fails. The original emergency wording is never stored; history records `(message not saved)` plus Baymax's reply, and persisted concern is nudged by 0.25. This records that a safety response occurred, so it is not a claim of zero trace. Regression tests and current CI are the verification gates.
- **F6, F7, F8, F9, F10, F11, F12** remain open.
- **AC-12 / AC-16:** Key exposure checks and recovery/verification of the original 48 tests remain unproven. The current suite was created for this snapshot and is not evidence that the prior suite passed.
- Live Gemini, browser UI, phone/PWA, and tunnel verification are still pending.

### Validation status for this follow-up

Changes were committed to the draft PR branch through GitHub. Local execution was not available in this session; GitHub Actions results must be checked before claiming the updated suite passes. PR #1 remains unmerged.
## Claude review follow-up — second implementation batch (2026-10-15)

### Implemented on `work/v0.6.1-hardening`

- **F6:** Added state-specific short-form closing intent handling for “shut down please”, “yes shut down”, and “let’s stop”, plus “keep going please”. Removed bare `stop` from ordinary exit-intent phrases to avoid starting the satisfaction ritual from that ambiguous word alone.
- **F7:** Full account deletion now attempts to remove pre-migration backup snapshots before deleting active rows, so a purge failure does not silently claim success. The delete-data disclosure identifies this side effect. This intentionally removes rollback snapshots in that data directory, not only a single account's copy.
- **F8:** HTTP request handlers use a 15-second socket timeout and suppress expected `BrokenPipeError` / `ConnectionResetError` when the client disconnects. Added timeout coverage.
- **F9:** User deletion no longer holds the global session-map lock while waiting for that user’s turn lock. Session reopening retries against a fresh session when a concurrent deletion invalidates the old one. Added a concurrency regression test.
- **F11:** Added narrow guards for figurative “project is a headache” and culinary “burning dinner” uses, while preserving literal pain detection. Added “chest feels tight” variants to the deterministic urgent-medical path and tests. The keyword system is still rule-based and needs broader clinical safety review.
- **F12 (partial):** Exports now include all ratings and daily usage; consent discloses the auto-memory default and commands to turn it off/on; export URL revocation is delayed; Python 3.10 was added to CI; API health/version and footer now use the package version; API/static not-found responses include stable error codes and common API validation errors carry codes. Digit redaction now consumes full long grouped sequences and avoids the reported all-two-digit-group false positive; ordinary "token was rejected" wording is no longer consumed as a secret value.

### Still open

- **F3 / AC-7 conflict:** No change made to emergency-turn persistence pending a product/privacy decision. Red-flag replies still do not access the model or storage.
- **F10:** The rebuilt web client still needs reconciliation with the original v0.6 UI. The original web assets and 48-test suite were absent from the source bundle available for this branch; they have not been recovered.
- **F12:** Broader adversarial redaction tests, web install icons, full consent/settings parity, and any remaining HTTP/API edge cases need further review.
- **AC-12 / AC-16:** LLM diagnostics now retain only the exception type, not raw SDK exception text, reducing the risk of returning keys/request details to the client. End-to-end key-exposure checks and equivalence to the original suite are still not proven. The current suite is newly authored.
- Real Gemini/model acceptance, browser visual QA, phone/PWA installation, tunnel/HTTPS and speech still require manual checks.

### Validation

GitHub Actions passed for push and pull-request workflows on commit `347f779`. Additional digit-redaction and LLM-exception-hardening commits were added afterward; their latest workflows must pass before merge. Local test execution was unavailable in this session. PR #1 remains open, draft, and unmerged.

## 2026-10-17 — F12 — Multi-word secret redaction hardening

- **Status:** Implemented; CI verification pending.
- **Architecture requirement:** AC-10 / F12 — redact secrets before model calls and persistence.
- **Files changed:** `baymax/safety.py`, `tests/test_detection_and_safety.py`.
- **Implementation notes:** Added a deterministic pre-pass for multi-word values assigned to secret labels (for example, `password is correct horse battery staple`) so the full value is redacted instead of only its first word. Added regression cases for password, passcode, and API-key assignment formats. The existing ordinary phrase test `the token was rejected` remains in the suite.
- **Tests run and results:** Focused regex cases were exercised in an isolated Python check and produced the expected redactions. The full repository test suite has not been run locally in this session. GitHub Actions for commit `69d61929d8befff3f2f602807c806bae6a1de89c` was queued at the time of this entry.
- **Known limitations / risks:** Redaction is heuristic. Multi-word assigned values are redacted through the next sentence/line boundary, which may also hide non-secret text in that span. This change does not establish complete secret-detection coverage.
- **Next step:** Verify the GitHub Actions result on the latest branch head, then continue the remaining F12 review items.


## F3 / AC-7 — emergency response persistence — 2026-10-23

- **Status:** Implemented in source; awaiting automated CI verification.
- **Files changed:** `baymax/service.py`, `tests/test_service.py`, `README.md`, `IMPLEMENTATION_LOG.md`.
- **Implementation:** Constructs the deterministic response first, then best-effort persists a neutral user placeholder and the assistant's safety reply, and nudges persisted concern by 0.25. Storage errors are caught and do not change the returned safety response. The original emergency wording is not persisted by this path.
- **Regression coverage added:** placeholder/reply-only persistence; concern increase; response survives storage failure; safety response preempts shutdown state while preserving the ritual.
- **Not verified by this edit:** live Gemini, phone/PWA/browser visuals, and deployment/HTTPS.
- **Important privacy qualification:** Although the original emergency words are not saved, the saved Baymax reply indicates that a safety event occurred.


## Round-two review follow-up — 2026-10-23

- **R2-1 / R2-2:** Urgent detection accepts missing, straight, and curly apostrophes for breathing/bleeding phrases. Added common self-harm phrases and a negative case for "don't want to leave the house". Curly apostrophes are normalized before detection, rating parsing, and redaction.
- **R2-3:** Multi-word secret redaction now stops before sentence punctuation so a following symptom report remains available for detection. Added regression cases for password/PIN sentences followed by pain/sadness disclosures.
- **R2-4:** Trusted-proxy client resolution now uses the final X-Forwarded-For entry when the direct peer is loopback and trusted-proxy mode is enabled. Added resolver tests. Actual proxy header behavior on the target host remains unverified.
- **R2-5:** Safety replies include the nudged concern value; only expected SQLite/OS errors are suppressed during best-effort persistence. Added tests for storage failure and for unexpected exceptions remaining visible.
- **R2-6:** Closing-choice matching no longer treats "finish" or "leave" as shutdown terms.
- **R2-7:** Full deletion removes active rows before attempting backup purge. A failed purge is returned as a warning instead of preventing deletion or falsely claiming snapshots were removed. README now explains that pre-migration backups may contain deleted data until successfully purged.
- **Tests added:** detection/redaction regressions, trusted-proxy resolver tests, safety emotion/error handling tests, and deletion/closing regressions.
- **Verification:** Changes were committed to work/v0.6.1-hardening; the latest suite and GitHub Actions results have not yet been verified after these commits. Real Gemini, browser/device and proxy deployment checks remain pending.


## Detection and redaction follow-up — 2026-10-23

- **R2 detection follow-up:** Narrowed self-harm expressions so ordinary contextual statements about not wanting to live in a city or not wanting to be at a meeting do not trigger the crisis hold. "End it all" now requires a first-person intent phrase and excludes constructions followed by "with" or "by". Added tests for both positive and negative examples.
- **Question/negation handling:** The general-question guard no longer mistakes "Can't ..." for a question. Apostrophe-less forms such as "dont", "cant", "wont", and "isnt" are recognized by the negation guard; tests cover "I dont have chest pain".
- **R2-3 follow-up:** PIN and OTP redaction is now numeric-only, with spaces/dashes allowed. The service passes redacted text to the brain/model and persistence, while raw text is supplied only to local deterministic difficulty detection. Episode snippets/context remain based on redacted text. The secret-only shortcut no longer overrides a locally detected difficulty or red flag.
- **Regression coverage added:** narrow self-harm matching; "Can't" difficulty detection; apostrophe-less negation; numeric-only PIN/OTP redaction; same-sentence secret plus symptom; punctuation preservation; ordinary password-status wording; service-level secret-plus-pain rating; and model-input/history redaction.
- **Verification:** GitHub Actions passed all 84 tests on Python 3.10, 3.11, and 3.12 for commit `7ace26bb7ec8567e5e89f69d2919ce5dcf56a891`. Real Gemini, browser/device and proxy deployment checks remain pending.


## Round 3 — R3-2 detection gaps — 2026-10-23

- **Status:** Implemented; focused regression tests pass. No version change.
- **Finding:** R3-2 (`REVIEW_PR1.md`): add the listed emergency/self-harm phrases while preserving the three specified harmless controls. Informational and third-person mentions intentionally remain unguarded, as accepted by the review.
- **Files changed:** `baymax/detection.py`, `tests/test_detection_and_safety.py`, `README.md`, `IMPLEMENTATION_LOG.md`.
- **Implementation:** Expanded urgent and self-harm phrase matching for breathing/air, choking, heart attack, overdose wording, not breathing, coughing blood, seizure, `wanna die`, wishes of being dead, lack of point in living, `kms`, waking up, and the bare first-person `don't want to be here` phrasing. Added the fail-safe limitation to the README.
- **Tests added:** `test_urgent_phrase_table`, `test_self_harm_phrase_table`, `test_harmless_controls_not_flagged`.
- **Verification:** Local focused tests passed: 3 tests.
- **Not verified at this item:** Full suite, browser/device behavior, real Gemini, and deployment/HTTPS.


## Round 3 — R3-1 exit during safety hold — 2026-10-23

- **Status:** Implemented; five focused regression tests pass. No version change.
- **Finding:** R3-1: the first typed exit or End-button request during an active self-harm hold must return one deterministic safety check; a second request may begin the normal shutdown ritual. The next normal chat turn clears the check flag.
- **Files changed:** `baymax/service.py`, `tests/test_service.py`, `IMPLEMENTATION_LOG.md`.
- **Implementation:** Added session-local `exit_checked`; both exit paths share a storage-independent response using the configured emergency hint. The reply does not claim that help was contacted. A second exit request proceeds to the existing satisfaction ritual; expired holds do not delay it.
- **Tests added:** `test_exit_during_hold_gets_safety_check`, `test_second_exit_starts_ritual`, `test_exit_after_hold_expires_goes_to_ritual`, `test_end_button_matches_bye`, `test_exit_check_works_with_dead_store`.
- **Verification:** The five named tests passed locally via `python -m unittest`.
- **Not verified at this item:** Full suite, browser/device behavior, real Gemini, and deployment/HTTPS.
