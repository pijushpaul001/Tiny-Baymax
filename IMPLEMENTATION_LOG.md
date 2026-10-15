# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Implementation snapshot:** v0.6.1 hardening candidate
- **Architecture:** Claude's detailed v0.6 architecture reviewed; use it as the contract for follow-up work.
- **Automated verification:** 41 tests passed locally; Python compile check and JavaScript syntax checks passed.
- **GitHub sync:** Source is being committed to `work/v0.6.1-hardening`. `main` remains documentation-only until the pull request is reviewed and merged.
- **Real Gemini / device verification:** Not run. These require the user's configured API key and phone/network environment.
- **Last updated:** 2026-10-13

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

1. Finish syncing and verify the source tree on `work/v0.6.1-hardening`.
2. Review the draft pull request against G1–G18 and AC-1–AC-16 in `CLAUDE_HANDOFF.md`; handle review findings in separate commits.
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

- **F3 / AC-7 conflict:** Claude recommends best-effort persistence of red-flag exchanges, but AC-7 explicitly says the emergency reply works with no storage access. No change was made to this contract pending a decision; emergency response remains independent of the model and storage.
- **F6, F7, F8, F9, F10, F11, F12** remain open.
- **AC-12 / AC-16:** Key exposure checks and recovery/verification of the original 48 tests remain unproven. The current suite was created for this snapshot and is not evidence that the prior suite passed.
- Live Gemini, browser UI, phone/PWA, and tunnel verification are still pending.

### Validation status for this follow-up

Changes were committed to the draft PR branch through GitHub. Local execution was not available in this session; GitHub Actions results must be checked before claiming the updated suite passes. PR #1 remains unmerged.