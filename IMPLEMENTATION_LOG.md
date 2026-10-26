# Tiny Baymax — Implementation Log

This log tracks implementation against `CLAUDE_HANDOFF.md`. Never record or commit API keys, passcodes, private health conversations, or other identifying/sensitive data.

## Current status — 2026-10-26

- **Repository:** `pijushpaul001/Tiny-Baymax`
- **Implementation snapshot:** v0.6.1 hardening candidate
- **Active branch:** `work/v0.6.1-hardening`
- **Latest source commit:** `5bd8b226` — `fix: narrow ambiguous self-harm matches`.
- **Latest test commit:** `d0180433` — `test: add N2 ambiguous self-harm coverage`.
- **Round 4 fixes:** N1 urgent-medical phrase coverage, N3 version assertion, N4 hosting documentation alignment, and N2 narrow self-harm matching are implemented.
- **Pull request:** PR #1 remains open and unmerged.
- **Post-N2 test execution:** Not yet run after the N2 source/test changes; do not treat earlier local test results as validation of this head.
- **CI status:** GitHub Actions on the latest head has not yet been established by this update.
- **Real Gemini / device verification:** Not run.
- **Main branch:** remains documentation-only until review/merge.

## Summary

| ID | Area | Status | Details |
|---|---|---|---|
| SETUP-001 | Repository coordination | Done | README, architecture/agent docs and implementation log retained. |
| PHASE0-001 | Tests / project hygiene | Done | CI workflow, regression tests, gitignore and manual-test documentation added. `tests/` and `web/` were architecture-guided additions because they were absent from the supplied source bundle. |
| G1/G13 | Rating capture | Done | Numeric/worded ratings, skip, correction, ambiguity and incidental-number handling covered by tests. |
| G2/G10 | Persistence / atomic writes | Done | Rating and related state persistence implemented and regression-tested. |
| G3 | Shutdown classification | Done | Negative satisfaction phrases are evaluated before positive phrases. |
| G4 | Exit intent | Done | Short whole-message exit phrases avoid broad false positives. |
| G5 | Feedback secret redaction | Done | Shutdown feedback is redacted before persistence. |
| G6 | Digit-group redaction | Done | Long grouped numeric secrets are handled without treating ordinary numeric text as a secret solely by length. |
| G7 | HTTP error handling | Done | Validation, SQLite and unexpected exception paths return structured errors. |
| G8 | CORS / OPTIONS | Done | Explicit origin allowlist; default allowlist is empty. |
| G9 | Failed-login throttling / trusted proxy | Done | Temporary lockout and opt-in trusted-proxy handling implemented and tested. |
| G11 | SQLite schema versioning | Done | Transactional baseline migration and pre-migration backups implemented. |
| G12/G15 | Safety-first path | Done | Urgent/self-harm detection precedes model calls; deterministic safety responses do not depend on Gemini. |
| G14 | Rating management | Done | Rating edit/delete API routes implemented. |
| G17 | User deletion encapsulation | Done | Deletion is handled through `ChatService.forget_user`. |
| F3 / AC-7 | Emergency persistence | Implemented | Safety response is constructed first; original emergency wording is not stored. Best-effort persistence records a neutral placeholder plus Baymax's reply and nudges persisted concern by 0.25. Storage failures do not change the returned safety response. |
| R2 | Detection/redaction hardening | Implemented | Apostrophe normalization, self-harm/urgent phrase coverage, multi-word secret handling, PIN/OTP numeric redaction, punctuation preservation and contextual false-positive controls added. |
| R3-1 | Exit during safety hold | Implemented | First exit request during an active self-harm hold gives a deterministic safety check; second request may start the normal ritual. |
| R3-2 | Detection gaps | Implemented | Additional urgent/self-harm phrases and harmless controls added. |
| R3-3 | Silent automatic memory | Implemented | Auto-memory remains silent in chat; saved facts remain inspectable/deletable in Settings. |
| R3-4 | Delete-all backup warning | Implemented | UI surfaces a server warning when backup purge fails. |
| R3-5 | Emergency guidance on failed sends | Implemented | Emergency guidance remains available on authentication/rate-limit/network failures. |
| R3-8 | Safety-path logging/shared replies | Implemented | Expected persistence failures log only exception type; deterministic emergency reply templates are shared. |
| N1 | Urgent-medical phrase coverage | Implemented | Added common chest-pain, breathing, heavy-bleeding, fainting/pass-out and severe-allergic-reaction phrasings to the deterministic urgent path. Added positive and negation regression tests. |
| N3 | Version assertion | Implemented | Web integration test now compares `/api/health` version with `baymax.__version__` instead of pinning `0.6.1`. |
| N4 | Phone hosting documentation | Implemented | README now follows the decided cloud-VM + Tailscale path: server bound to `127.0.0.1`, Tailscale provides HTTPS/private access, persistent disk and single-process hosting. |
| N2 | Self-harm false positives | **Implemented** | Narrowed only the two agreed ambiguous patterns. `kms` is exempted after numeric/number-word/quantity contexts and when followed by `away`, `from`, or `per`. `don't want to wake up` is exempted only for clearly harmless time/routine continuations such as `at 5am`, `early`, `late`, `so early`, and `for work/school/class`. Bare and explicitly self-harm-adjacent continuations remain flagged. Added regression coverage for the agreed no-flag and flag examples. |
| UI-001 | Web client | Implemented; browser review pending | Responsive browser/PWA client exists with consent, ratings, shutdown controls, data controls and emergency guidance. Visual/browser QA remains outstanding. |
| VERIFY-001 | Real-world verification | **Not started** | Real Gemini, browser/device, HTTPS/proxy and deployment checks remain. |
| MOBILE-001 | Native Android shell | Later phase | Outside the current hardening snapshot. |
| REMIND-001 | Reminders | Deferred | v0.7.0 reminder work remains out of scope. |

## Current validation — 2026-10-26

- N2 source and regression-test changes have been committed.
- The full test suite has **not yet been run after the N2 changes**.
- GitHub Actions on the latest head has not yet been established by this update.
- Browser smoke with `BAYMAX_LLM=fake` remains outstanding.
- Real Gemini, HTTPS/Tailscale, device/PWA and deployment verification remain outstanding.

## Known limitations / risks

1. No actual Gemini request has been performed. Model availability, quota behaviour, structured-output behaviour and real reply quality remain unverified.
2. No real browser visual QA, phone/PWA installation, HTTPS/Tailscale route, speech test or native Android build has been performed.
3. Session-only state such as active rating waits, shutdown ritual and safety hold remains in process memory and resets after server restart.
4. Consent is enforced in the web UI; this does not establish legal or regulatory compliance.
5. The supplied source bundle did not contain the original `tests/` or `web/` directories. The current tests and web client are architecture-guided additions, so equivalence to the original missing test suite/UI is not proven.
6. The latest N2 source/test changes require fresh local and CI validation before the branch can be considered merge-ready.
7. `main` and deployment should not be treated as release-ready until PR review/merge and manual verification are complete.

## Next steps

1. Run the full local test suite against the latest N2 head and record the result.
2. Verify GitHub Actions on the latest branch head and record the result separately from local verification.
3. Run the browser smoke test from `docs/MANUAL_TEST.md` with `BAYMAX_LLM=fake`.
4. After the merge gate is satisfied, address R3-6 (Gemini error codes) and R3-7 (merge adjacent same-role messages) before Phase 2 real-Gemini verification.
5. Only after those checks pass, run real Gemini and the phone/Tailscale path, then consider the native Android shell.

## Historical implementation record

The branch history contains the detailed implementation/review sequence. Major recorded work includes:

- F1/F2/F4/F5 review fixes for shutdown answers, direct account controls, rating phrasing and trusted-proxy handling.
- F6/F7/F8/F9/F11/F12 hardening for closing intent, deletion/backup handling, HTTP timeouts, deletion concurrency, contextual safety detection and secret/error redaction.
- Multi-word secret redaction and PIN/OTP handling.
- F3/AC-7 deterministic emergency response persistence with neutral placeholders and concern nudging.
- R2-1 through R2-7 detection, redaction, proxy, safety persistence and deletion refinements.
- R3-1 through R3-5 and R3-8 safety-hold exit handling, detection expansion, silent memory UI, delete-all warning propagation, emergency guidance on failed sends, and safety logging/shared replies.
- Round 4 N1, N3, N4 and N2 fixes are now recorded above.
