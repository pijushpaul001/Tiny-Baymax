# Review of PR #1 — `work/v0.6.1-hardening` (commit b18e7b6)

Reviewer: Claude. Reviewed against `CLAUDE_HANDOFF.md` (G1–G18, AC-1–AC-16). No code was modified.

## 1. Source access

The GitHub pages could not be read by my web tool (robots block), so the review used the uploaded ZIP `Tiny-Baymax-work-v0_6_1-hardening.zip`. It contains all the files named in the request: `baymax/service.py`, `decision.py`, `storage.py`, `server/app.py`, `server/api.py`, `tests/` (5 test files) and `web/` (6 files). I could not confirm the ZIP matches commit b18e7b6 exactly (no `.git` metadata was inspected). CI results on GitHub were not visible to me.

## 2. What was verified, and how

**Verified by running code in a sandbox (Python 3.12.3, FakeLLM, no network):**
- `python -m unittest discover -s tests -t .` → 41 tests, OK. (`google-genai` was not installed, so `baymax/llm/gemini.py` was never imported.)
- 16 targeted repro scripts (listed per finding below), run against the branch's real classes and a real `ThreadingHTTPServer`.

**Verified by reading only:** everything cited as "code reading".

**NOT verified (needs real Gemini, a browser or a phone):**
- Real Gemini: model name `gemini-3.5-flash-lite` accepted, structured-output schema accepted, JSON not truncated at `max_output_tokens=700` (`llm/gemini.py`), retry/fallback behaviour.
- Browser rendering and behaviour of `web/`: rating chips, quick replies, consent dialog, offline card, End-session flow, export download, service worker offline behaviour, PWA install (icon requirements), voice. I read `web/app.js` and `index.html` but did not run them in a browser.
- HTTPS / Tailscale / tunnel behaviour. F4 below was reproduced at the `Auth` level with identical client ids; I did not run it through a real proxy.
- Start-up refusal on a read-only directory (the sandbox runs as root, so I used a path under a file and a corrupt DB instead; both refused to start).
- Behaviour under load or concurrent users beyond F9.
- GitHub Actions results.

## 3. Status of G1–G18

| ID | Status | Notes |
|---|---|---|
| G1 skip/correct | **Fixed**, verified | skip records nothing; "actually 6" updates the stored row. Residual gaps in F5. |
| G2 rating lost on model failure | **Fixed**, verified | rating row persisted when `FakeLLM` raises. |
| G3 "very" = satisfied | **Fixed** for prefix cases, verified | "very disappointed", "not satisfied" go to feedback. New problems in F1. |
| G4 exit intent | **Partly** | exact-phrase set + End button work; "stop" newly starts the ritual; closing-state phrases in F6. |
| G5 feedback unredacted | **Fixed** (code reading `service.py:162`; test exists) | |
| G6 spaced digit redaction | **Fixed**, verified | card and 12-digit IDs redacted; false positives and a 24-digit tail leak in F12. |
| G7 HTTP error handling | **Fixed**, verified | JSON 500/503/400; `BrokenPipeError` still escapes (F8). |
| G8 CORS/OPTIONS | **Fixed**, verified | allow-listed origin gets 204 + headers. |
| G9 login lockout | **Implemented, but wrong key behind a proxy** | F4. |
| G10 atomic persistence | **Fixed** (`Store.persist_turn`; rollback test exists) | |
| G11 schema versioning | **Fixed**, verified | legacy DB (`user_version` 0) → 1 with backup. Backups outlive delete-all (F7). |
| G12 emergency independent of storage/model | **Fixed**, verified | works in every ritual state with a dead store. Side effect in F3. |
| G13 numeric parse | **Partly** | incidental numbers rejected correctly; legitimate phrasings rejected (F5). |
| G14 rating edit/delete | **Fixed** (API + UI code; tests exist) | |
| G15 not-medical-advice line | **Fixed** (`decision.py:77-83`) | |
| G16 contractions | **Mostly** | leftovers: `decision.py:197` "you're", `safety.py:9`, `service.py:242`. Optional. |
| G17 `forget_user` | **Fixed**, but see F9 | |
| G18 session state in memory | Unchanged (documented, optional) | |

## 4. Status of AC-1 to AC-16

| AC | Status | Evidence / finding |
|---|---|---|
| AC-1 greeting | Met | `constants.GREETING` unchanged; `open_session` unchanged. |
| AC-2 pain/sad → immediate rating, no model | Met (verified) | scale and "You can also say skip" present. |
| AC-3 normal life → no rating | **Not met** | F11: "this project is a headache" asks a pain rating (pre-existing, not a regression). |
| AC-4 rating/skip/correction/incidental numbers | **Mostly** | works for the tested forms; F5 for legitimate phrasings. |
| AC-5 rating survives model failure | Met (verified) | |
| AC-6 ritual | **Partly** | F1, F6. |
| AC-7 emergency without model/storage, in every state | Met (verified) | reply includes the not-medical-advice line. F3 is a side effect. |
| AC-8 failure handling | Met (verified) / partly | model failure, dead SQLite (exception → 503), bad data dir, corrupt DB (exit 1, file untouched). |
| AC-9 inspect/export/delete | **Partly** | F7 (backups), F12 (export caps ratings at 1000, omits `usage`). |
| AC-10 redaction incl. feedback | Met, with caveats | F12. |
| AC-11 no sensitive auto-memory | Met | `memory_gate` logic unchanged. |
| AC-12 key never in app/logs | Not verifiable here | no key reference in `web/`; no end-to-end check done. |
| AC-13 consent before first message | **Partly** | client-side only (documented); consent text omits auto-memory (F12). |
| AC-14 passcode storage + lockout | **Partly** | passcode kept in JS memory only; lockout F4. |
| AC-15 emotion changes behaviour, no clingy/real-feeling claims | Not re-verified | existing logic unchanged; F3 means safety turns do not move emotion. |
| AC-16 existing tests still pass | **Cannot be assessed** | the original 48 tests are not in the repo; the 41 present are new and pass. |

## 5. Findings

Severity: **H** violates a non-negotiable or can lock the owner out; **M** wrong or unsafe behaviour with a workaround; **L** polish/robustness.

### F1 — M — "Yes …" ends the session and drops whatever follows
- **Where:** `baymax/service.py:21-24` (YES), `25-28` (NO), `158-159` (YES.match → `_finish`).
- **Behaviour:** both patterns are prefix matches. Anything after the first word is silently discarded.
- **Repro:** `bye` → `yes but my head hurts really bad` → `ended=True`, no rating question, no rating row. Also `bye` → `no problem, I am satisfied` → treated as NOT satisfied (goes to feedback).
- **Fix:** accept only whole short replies (≤4 words after stripping punctuation) that match; anything longer is "unclear" → `s.closing = None` and the message goes down the normal path so pain/sadness detection runs. Treat "no problem"/"no worries" as affirmative.
- **Regression tests:** `test_yes_with_pain_report_is_not_a_goodbye` (expects `ended is False` and a rating question); `test_no_problem_i_am_satisfied_is_positive`.

### F2 — M — API buttons are swallowed while the ritual waits for feedback
- **Where:** `service.py:161-166` (the `feedback` state consumes any text); `server/api.py:71` (`/api/memories` POST), `95` (`/api/clear`), `97` (`/api/emotion/reset`) all route through `svc.handle`.
- **Behaviour:** if the ritual is in `feedback`, "Clear conversation", "Reset state" and adding a memory are stored as feedback text and do nothing.
- **Repro:** `bye`, `no` → `POST /api/clear` → reply is "Thank you for telling me…", history not cleared (3 rows remain), and `/remember my favourite food is dosa` ends up in the `feedback` table. Breaks "user can always clear/reset".
- **Fix:** give `ChatService` direct methods (`remember(uid, fact)`, `clear_history(uid)`, `reset_emotion(uid)`) and call them from the API; or let `/…` commands bypass the ritual states.
- **Regression tests:** in `feedback` state, `/api/clear` empties history and writes nothing to `feedback`; same for `/api/memories`.

### F3 — M — Emergency turns leave no trace, so Baymax forgets them
- **Where:** `service.py:144-150` and `_safety_resp` `103-108`.
- **Behaviour:** the reply is correct and storage-independent (good), but nothing is saved afterwards: no messages, no concern increase, and the response reports baseline emotion. In v0.6.0 the exchange was stored and concern rose.
- **Repro:** `I want to die` → history rows added: 0; stored emotion `{}`; next turn the model sees only the greeting, and `concern` stays 0.10. After the 3-turn hold ends nothing remembers the disclosure, and `style()` can allow humour again.
- **Fix (agreed 2026-10-17):** generate and return the emergency reply first, exactly as now. Then, in a `try/except sqlite3.Error` that can never change or delay the reply, persist: (a) Baymax's emergency reply as an assistant message, preceded by a neutral placeholder user message (for example "(message not saved)") so roles keep alternating for Gemini; (b) the existing concern nudge (+0.25). **Never store the user's emergency message itself.** Applies to both self-harm and urgent-medical replies. Normal turns are unchanged.
- **Honest limit:** the saved reply text itself shows that a safety reply was given, so the history still records the category of event, but not the user's words. Say this in the README privacy section.
- **Regression tests:** (1) with a healthy store, history gains the reply and the placeholder, and the user's text appears nowhere in any table; stored concern rises by about 0.25. (2) With a store that raises, the reply is still returned unchanged. (3) The next model call after an emergency sees the assistant's safety question in its history. (4) A normal turn after the hold stores messages exactly as before.

### F4 — M — One client can lock the owner out, especially behind a proxy
- **Where:** `server/app.py:77` (`client_id = self.client_address[0]`), `server/auth.py:38-39` (a locked client gets `None` even with the correct token).
- **Behaviour:** with `tailscale serve` or a tunnel (the README's recommended setups) every request arrives from the local proxy address, so all users share one id. Five wrong guesses lock everyone for 60 s, repeatable indefinitely on a public tunnel.
- **Repro (Auth level):** 5 bad tokens with `client_id="127.0.0.1"` → correct token with the same id → `None`; with `10.0.0.9` → owner.
- **Fix:** add `BAYMAX_TRUSTED_PROXY` (off by default). When set, take the client from the `X-Forwarded-For` entry **only if the peer is a loopback address**. (Correction, round 2: use the *last* entry, not the first; see R2-4.) Optionally let a correct token succeed during lockout when it comes from a client that previously authenticated, or lock per (client, attempted-token-prefix). Document the choice.
- **Regression tests:** with the setting on, two different forwarded clients are locked independently; with it off, `X-Forwarded-For` is ignored (cannot be spoofed).

### F5 — M — Rating parser rejects common phrasings and mis-reads "seven out of ten"
- **Where:** `baymax/detection.py:93` (`_NUMBER_TOKEN`), `124-130` (candidate counting), `133-141` (`allowed_prefix`), `89` (`_SKIP_RATING`).
- **Behaviour:** `seven out of ten` → **ambiguous** (seven and ten counted as two numbers; v0.6.0 returned 7); `it is about a six`, `i'd say about a six`, `its 7`, `like a 7`, `pretty bad, maybe 7`, `7 pain` → none; `i'd rather skip`, `skip it` → none (not skip).
- **Fix:** strip `out of (10|ten)` and `/10` before collecting candidates; allow filler sequences (`(it is|it's|its|i'd say|about|around|like|maybe|probably)` repeated, plus a short trailing word list); accept skip phrases that merely contain "skip"/"rather not" in a ≤5-word message.
- **Regression tests:** table test: each phrase above → expected kind/value; keep negatives (`i took 2 pills`, `meet at 3 pm`, `3 tablets`) → none.

### F6 — L/M — Closing-state phrases are too exact
- **Where:** `service.py:167-173` (`KEEP.fullmatch`, `is_exit_intent` exact set).
- **Behaviour:** after "Would you like to keep going, or shall I shut down?": `shut down please`, `yes shut down`, `let's stop` → ritual silently dropped and the model chats on (user not trapped, but the request is ignored).
- **Fix:** in `decide` state only, match short messages (≤5 words) containing a stop/shut word or a keep/continue word.
- **Regression tests:** those three phrases → `ended=True`; `keep going please` → continues with an acknowledgement.

### F7 — M — "Delete everything" leaves private data in `.bak` files
- **Where:** `storage.py:294-298` (`delete_all`), `65-82` (`_backup_before_migration`).
- **Repro:** legacy DB with a chat → `Store(...)` creates `baymax.db.pre-migration-….bak` → `delete_all` → main DB empty, **`.bak` still contains "my private chat"**.
- **Fix:** document it in README and the delete-all dialog, and add a `purge_backups()` step called by `forget_user` when it is the only user (or an `/api/data` option). At minimum, shorten retention and say so.
- **Regression test:** after `forget_user` on a single-user store, no `.bak` file contains that user's text (or the response lists remaining backups).

### F8 — L/M — No socket timeout; noisy broken-pipe traces
- **Where:** `server/app.py:45-47` (`Handler.timeout` is `None`), `75` (`rfile.read`), `63`/`85` (write outside the try).
- **Repro:** half-sent request keeps a server thread occupied indefinitely; client disconnect during write prints a `BrokenPipeError` traceback.
- **Fix:** `timeout = 15` on the handler; wrap the final write in `try/except (BrokenPipeError, ConnectionResetError)`.
- **Regression test:** a stalled connection is dropped within the timeout (use a small value in the test).

### F9 — L — `forget_user` blocks every session while a slow turn finishes
- **Where:** `service.py:117-127` (holds `self._guard` while waiting for the session lock).
- **Repro:** slow model call for user A + `forget_user(A)` → an unrelated user's `open_session` blocked 2.4 s (equal to the remaining turn time).
- **Fix:** detach the session under `_guard`, release it, then take the session lock and delete.
- **Regression test:** with a 2 s model call in flight, another user's `open_session` returns in < 0.5 s while `forget_user` is pending.

### F10 — M (product) — The rebuilt `web/` lacks features of the original v0.6 app
- **Where:** `web/app.js` (no speech input/output, no use of `emotion` beyond reset), `web/index.html` (no face, no settings toggles), `web/manifest.webmanifest` (SVG-only icon).
- **Behaviour:** no Baymax face following the emotion state, no voice in/out, no auto-memory or speak toggle (users must type `/memory-off`), passcode must be retyped on every reload (`app.js:179`). The `/api/state` endpoint is unused.
- **Not verified in a browser.** PWA install may need PNG icons (and iPhone needs an `apple-touch-icon`).
- **Fix:** first recover the original `web/` and `tests/` from `tiny-baymax-v0.6.zip` if it still exists, and diff them against this PR. If not recoverable, create a task for: face (eye size/blink from emotion), speech in/out through the planned `platform.js` bridge, a settings panel (auto-memory, speak), a PNG icon set.
- **Regression test:** extend `test_web_integration.py` to assert the index references a settings panel and that the manifest has a ≥192 px PNG icon.

### F11 — M (pre-existing) — Keyword detection triggers pain ratings in normal life
- **Where:** `baymax/detection.py:10` (PAIN), `13` (EMOTION).
- **Repro:** `this project is a headache` → physical/pain → rating question; `I am burning dinner` → same. Violates AC-3 and rule 1 ("never for normal life"). Also `my chest feels tight` is not detected at all, and `I would never hurt myself` triggers the self-harm reply (intentional fail-safe, noted for the user).
- **Fix:** add an idiom/figurative guard (`headache` after `is a`/`what a`, `burning` after a transitive verb or with food nouns), plus tests. Consider letting the model flag `difficulty.detected` as a *second opinion that can only downgrade* a rating request, never trigger an emergency.
- **Regression tests:** the examples above → no rating question.

### F12 — L — Smaller items
- **Export incomplete:** `storage.py:289-292` limits ratings to 1000 and omits `usage`.
- **Error envelope:** spec B.6 asked for `code` on error responses; `api.py:40,42,50,79,85,91,105` have none (the 401 body is `{"error": "Passcode needed."}`).
- **Version string** hard-coded in `api.py:34` and `index.html:82`; derive from `baymax.__version__`.
- **CI** matrix (`.github/workflows/tests.yml:14`) lacks 3.10 although the README says 3.10+.
- **Redaction:** `safety.py:8` redacts 12+ digit runs with spaces, so `10 20 30 40 50 60` becomes `[REDACTED]`; a 24-digit number leaves its last 8 digits (`7890 1234`); the keyword rule consumes the next word (`the token was rejected` → `the token [REDACTED] rejected`, pre-existing).
- **Consent:** dialog (`index.html:85-98`) does not mention auto-memory, which the spec (section D) listed.
- **Exit phrase:** `stop` alone now starts the shutdown question (`service.py:31-35`).
- **Export download:** `app.js:263-264` revokes the blob URL immediately; some mobile browsers cancel the download. Delay revocation.
- **G16 leftovers:** see table.
- Each needs a small test (see names in the table above or follow the pattern of existing tests).

## 6. Process notes
- `IMPLEMENTATION_LOG.md` marks G9, G11, G13 and G17 as "Done"; each has a residual issue above (F4, F7, F5, F9).
- The log says the 41 tests are new. The original v0.6.0 tests (48) and `web/` are not in the repo; recover them before merging (AC-16, F10).
- Features beyond Phase 1 (consent screen, chips, web client) were added; they are reasonable but need browser verification before they are counted as done.

## 7. Verdict and order (updated 2026-10-17 for the "simple first" scope, `CLAUDE_HANDOFF.md` section H)

**Verdict: changes requested. Do not merge PR #1 yet.** Fix the items below as separate commits on the same branch, each with its regression test, and log them in `IMPLEMENTATION_LOG.md`.

- **Required before merge:** F1, F2, F3, F5, F4, F7.
- **After the Android build, in this order:** F6, F8, F9, F11, F12.
- **F10 (face and voice):** now Phase 3a, defined in section H-2 and H-3. Do not add other UI features.
- **Do not build:** reminders, tools, summaries or anything else listed as deferred in section H-1.

## 8. Original suggested order (superseded by section 7)
1. F1, F2, F3, F5 (behaviour users will hit).
2. F4, F7 (access and privacy).
3. F6, F8, F9, F11, F12.
4. Phase 2 manual verification (real Gemini, browser, phone) before any Phase 3 work.


---

# Round 2 review: commit 87c3694 (2026-10-23)

Source: uploaded ZIP of branch `work/v0.6.1-hardening`; commit id read from the archive comment (`87c369469c8d270e9f07b751357e41e3ea6792e8`). I ran the suite and my repro scripts myself. GitHub Actions results are still not visible to me.

**Tests:** `python -m unittest discover -s tests -t .` → **63 tests, OK** (Python 3.12.3, FakeLLM). Up from 41.

## Round 1 findings: status (verified by running)

| ID | Status | Evidence |
|---|---|---|
| F1 | **Fixed** | "yes but my head hurts really bad" and "yes my head hurts" no longer end the session and the pain rating question is asked; "no problem, I am satisfied" ends; "very disappointed", "not satisfied" go to feedback. |
| F2 | **Fixed** | in the feedback state `POST /api/memories` saves the memory (0 feedback rows) and `POST /api/clear` empties history and resets the ritual. |
| F3 | **Fixed, with caveats R2-5** | user words ("want to die", "hunter2") appear in no table; history gains `(message not saved)` + the safety reply; stored concern 0.10 → 0.35; the next model call sees "Are you safe…" and roles alternate; a store that raises still returns the reply. |
| F4 | **Implemented, but see R2-3** | opt-in `BAYMAX_TRUSTED_PROXY`; ignored for non-loopback peers. |
| F5 | **Fixed** | "seven out of ten", "it is about a six", "i'd say about a six", "its 7", "like a 7", "pretty bad, maybe 7", "7 pain" → value; "i'd rather skip", "skip it" → skip; "7 or 8" → ambiguous; "i took 2 pills", "meet at 3 pm", "3 tablets", "I'm 7 years old" → none. |
| F7 | **Fixed** | `forget_user` removes the `.bak` snapshot and all rows. Caveat R2-4. |
| F8 | **Fixed** (code reading + attribute check) | `Handler.timeout = 15`; broken pipe is caught in `_send`. The broken-pipe path was not exercised. |
| F9 | **Fixed** | an unrelated user's `open_session` blocked 0.00 s (was 2.4 s). |
| F10 | Not started (Phase 3a) | |
| F11 | **Partly fixed** | "this project is a headache" and "I am burning dinner" no longer ask for a rating. "my chest feels tight" is now an emergency reply (new pattern). |
| F12 | **Mostly fixed** | export includes all ratings and `usage`; error `code` fields; version from `__version__`; 24-digit number fully redacted; `10 20 30 40 50 60` kept; "the token was rejected today" kept. CI matrix and G16 leftovers not re-checked. |
| F6 | **Fixed in code** (not re-run); see R2-6 | |

## New findings

### R2-1 — H — Safety regression: "cant breathe" and "wont stop bleeding" no longer trigger the emergency reply
- **Where:** `baymax/detection.py:16` (`URGENT`). The optional apostrophes were removed (`can'?t` → `can't`, `won'?t` → `won't`).
- **Repro (old snapshot vs new):** `detect("I cant breathe")` and `detect("it wont stop bleeding")` → `urgent_medical` before, **no flag now**. Phones and fast typists often drop the apostrophe.
- **Related, pre-existing:** the curly apostrophe `’` (common from phone keyboards) never matched: `detect("I can’t breathe")` → no flag in either version.
- **Fix:** restore the optional apostrophe and accept both kinds (`can['’]?t`, `won['’]?t`), and normalize `’` and `‘` to `'` once at the start of `detect()`, `redact_secrets()` and `parse_rating_reply()`.
- **Regression tests:** parametrized over `cant`, `can't`, `can’t`, `wont stop bleeding`, `won’t stop bleeding` → `urgent_medical`.

### R2-2 — M (pre-existing safety gap) — Common self-harm phrasings are not detected
- **Where:** `baymax/detection.py:17` (`SELF_HARM`).
- **Repro:** `detect("I don’t want to live")` and `detect("I dont want to live")` → no flag.
- **Fix:** add carefully chosen phrasings such as `don['’]?t want to (?:live|be here|be alive)`, `no reason to live`, `better off dead`, `end it all`, `take my own life`. Over-triggering is the safe direction here.
- **Regression tests:** each phrase → `self_harm`; harmless sentences ("I don't want to leave the house") → no flag.

### R2-3 — M — Redaction swallows the rest of the message after a password sentence
- **Where:** `baymax/safety.py:7-19` (`_MULTIWORD_SECRET_RX`); the value group `\S+(?:\s+\S+)+?` takes the full stop with the first word, so the "stop at sentence end" lookahead never fires.
- **Repro:** `my password is hunter2. My head hurts really bad` → `my password [REDACTED]` (the pain report is lost, so no rating question). `my pin is 4821. I feel sad today` → `my pin [REDACTED]`. Emergency detection is unaffected because it runs on the raw text first.
- **Fix:** stop the value at the first sentence terminator (`.`, `!`, `?`, `;`, newline); a trailing full stop is not part of the value.
- **Regression tests:** both sentences above keep their second sentence; `password is correct horse battery staple` is still fully redacted.

### R2-4 — M (my spec error) — Proxy client id uses the first `X-Forwarded-For` entry, which a client can forge
- **Where:** `server/app.py` `resolve_client_id` (`forwarded_for.split(",", 1)[0]`). I wrote "first entry" in the spec; that was wrong for a proxy that appends.
- **Repro:** `resolve_client_id("127.0.0.1", "6.6.6.6, 100.64.0.5", True)` → `6.6.6.6` (the attacker's value, while the real client is `100.64.0.5`). A forger can rotate fake ids to dodge the lockout, or frame another address.
- **Fix:** with one trusted proxy on the same machine, take the **last** entry. Update the spec text accordingly. How `tailscale serve` sets this header is unverified; check on the real host.
- **Regression tests:** the example above → `100.64.0.5`; single entry unchanged; non-loopback peer unchanged.

### R2-5 — L — `_safety_resp` hides all errors and reports baseline emotion
- **Where:** `baymax/service.py` `_safety_resp`.
- **Behaviour:** `except Exception: pass` hides programming errors. The response still shows concern 0.10 while 0.35 is stored, so the face would not react on the emergency turn.
- **Fix:** catch `sqlite3.Error` and `OSError` only (log the exception type, never content); return the nudged emotion in the response (computed from baseline if the store is down).
- **Regression tests:** response concern ≥ 0.35 with a healthy store; unexpected exception types are not swallowed in tests.

### R2-6 — L — Closing-state matcher is slightly too broad
- **Where:** `baymax/service.py` `_closing_should_end` (`end|finish|leave`).
- **Behaviour:** after the shut-down question, "I need to finish my homework" (5 words) ends the session.
- **Fix:** drop `finish` and `leave`; keep `stop|shut|shutdown|quit|exit|bye|goodbye|end`; keep the negation check.
- **Regression tests:** "I need to finish my homework" continues; "shut down please", "let's stop" end.

### R2-7 — L — `forget_user` purges backups before deleting data
- **Where:** `baymax/service.py` `forget_user`: `purge_backups()` precedes `delete_all`, and an `OSError` from `unlink` aborts the deletion (500, user data left in place).
- **Fix:** delete the user's rows first, then purge backups; if the purge fails, report it in the response and let the user retry. Note in the README that purging removes all pre-migration snapshots.
- **Regression test:** with `unlink` forced to raise, the rows are still deleted and the failure is reported.

### R2-8 — L — Log out of date
`IMPLEMENTATION_LOG.md` still says F3 awaits CI and cites 41 tests. Current local result: 63 passed.

## Round 2 verdict

**Not ready to merge.** Fix **R2-1** (safety regression) and **R2-3** (redaction swallowing a symptom report) first; **R2-2** (self-harm phrasings) and **R2-4** (proxy spoofing) next, since the proxy setting will be used for the cloud host. R2-5 to R2-8 can follow in the same branch. After these, remaining gates are: GitHub Actions green, a real Gemini run, and a phone/browser pass.


---

# Round 3 review: commit 68f1653 (2026-10-23)

Source: uploaded ZIP of branch `work/v0.6.1-hardening`; commit id read from the archive comment (`68f1653ba9fc04afe68339c8f9fd14b6e6d2566d`). No `.git` metadata was inspected. `CLAUDE_HANDOFF.md` and `REVIEW_PR1.md` inside the ZIP are identical to the copies I hold.

## 1. What was verified, and how

**Run by me (Python 3.12.3, FakeLLM, no network):**
- `python -m unittest discover -s tests -t .` → **84 tests, OK** (up from 63).
- Four probe scripts (about 70 cases): detection and redaction tables, service flows through every ritual state, a real `ThreadingHTTPServer` over HTTP (lockout, CORS, malformed requests, oversize body, traversal, delete-all), a real-file SQLite store with a forced `unlink` failure.

**Read in full:** every file under `baymax/`, `server/`, `web/`, plus `README.md`, `AGENTS.md`, `.env.example`, CI workflow, `docs/MANUAL_TEST.md`.

**NOT verified:**
- GitHub Actions on this commit. `IMPLEMENTATION_LOG.md` cites a green run for `7ace26b`; HEAD is `68f1653` and I cannot see its run.
- Python 3.10 and 3.11 (I ran 3.12 only).
- Browser behaviour of `web/` (chips, consent dialog, offline card, service worker, install). Read only.
- Real Gemini (model name, structured output, truncation, alternation of roles).
- Proxy header behaviour on the target host.
- That the ZIP equals the commit.

## 2. Round 2 findings: status

| ID | Status | Evidence |
|---|---|---|
| R2-1 | **Fixed**, verified | `cant`, `can't`, `can’t`, `wont stop bleeding`, `won’t stop bleeding` → `urgent_medical`; curly apostrophes normalised in `detect`, `redact_secrets`, `parse_rating_reply`. Wider phrase gaps: R3-2. |
| R2-2 | **Fixed** for the tested phrases | `don’t want to live`, `…anymore`, `…like this`, `better off dead`, `end it all` (first-person) detected; "I don't want to live in this city" and "I don't want to leave the house" are not. More phrasings missing: R3-2. |
| R2-3 | **Fixed** | "my password is hunter2. My head hurts really bad" keeps the second sentence; PIN/OTP numeric-only; `password is correct horse battery staple` fully redacted. Residual (L): `my password is hunter2 and my chest hurts` redacts the whole tail for the model and the history. Local detection runs on raw text, so the rating question still fires. Accepted. |
| R2-4 | **Fixed**, verified | `resolve_client_id("127.0.0.1", "6.6.6.6, 100.64.0.5", True)` → `100.64.0.5`; non-loopback peer, garbage and trailing-comma headers fall back to the peer. |
| R2-5 | **Fixed**, one gap | response concern 0.35 with a healthy store; only `sqlite3.Error` and `OSError` caught. The error is swallowed silently, see R3-8. |
| R2-6 | **Fixed**, verified | "I need to finish my homework" continues; "shut down please", "let's stop", "yes shut down", "please end this" end; "I don't want to stop" continues. |
| R2-7 | **Fixed in the service**, verified | rows deleted first; with `Path.unlink` forced to raise: `deleted: True, backups_purged: False, warning, backup_error`. **The web client ignores the warning**, see R3-4. |
| R2-8 | **Partly** | log updated, but its CI statement covers `7ace26b`, not HEAD. |

Still open from earlier rounds: F10 (face, voice, settings panel, PNG icons; Phase 3a), AC-12 and AC-16 (no key-exposure end-to-end check; the original 48 tests are still not in the repo), G16 leftovers.

## 3. New findings

Severity: **H** violates a non-negotiable or endangers the user; **M** wrong or unsafe behaviour with a workaround, or a broken user decision; **L** polish.

### R3-1 — M (safety, spec gap) — The shutdown ritual can end the session straight after a self-harm disclosure
- **Where:** `baymax/service.py:284-287` (exit intent) and `end_session`. Neither looks at `safety_hold_until`.
- **Repro (verified):** `I want to die` → safety reply → `bye` → "Are you satisfied with my care today?" → `yes` → "I am glad to hear that. Take care. Goodbye." `ended=True`. The hold is meant to keep Baymax steady for three turns; the ritual walks past it. My spec did not cover this case, so this is a spec gap as much as a code gap (see new C13 and AC-18).
- **Fix:** while the safety hold is active, the **first** exit request (typed or End button) gets one deterministic reply instead of the ritual: a short safety check in Baymax's manner that restates the emergency hint and says the user may say goodbye again to finish. Set `s.exit_checked = True`. A **second** exit request goes through the normal ritual, so the user is never trapped. Reset `exit_checked` on the next normal chat turn. Wording is for ChatGPT to propose; the "supportive information, not medical advice" line is not needed again here. Do not claim help was contacted.
- **Regression tests:** (1) self-harm → `bye` → reply is the check, `closing is None`, `ended is False`; (2) `bye` again → ritual question; (3) after the hold expires, `bye` goes straight to the ritual; (4) End button behaves like `bye`; (5) the check works with a dead store.

### R3-2 — M (safety, mostly pre-existing) — Common emergency and self-harm phrasings are still not detected
- **Where:** `baymax/detection.py:16` (`URGENT`), `17-24` (`SELF_HARM`).
- **Repro (verified, all → no flag):** urgent: `I can't catch my breath`, `can't get air`, `I can not breathe`, `I'm choking`, `I think I'm having a heart attack`, `I took too many pills`, `he is not breathing`. Self-harm: `i wanna die`, `I wish I was dead`, `no point in living`, `life is not worth living`, `kms`, `don't want to wake up`, `I dont want to be here` (without "anymore").
- **Fix:** add patterns for these (`wanna die`, `wish i (?:was|were) dead`, `no point (?:in )?(?:living|going on)`, `not worth living`, `heart attack`, `choking`, `catch my breath`, `(?:can(?:'|’)?t|cannot|can not) (?:get|catch)\b.*\b(?:air|breath)`, `too many (?:pills|tablets)`, `not breathing`, `coughing up blood`, `seizure`). Over-triggering is the safe direction here. Keep the existing harmless negatives.
- **Regression tests:** every phrase above → expected flag; harmless controls ("I don't want to leave the house", "I can't get this bug to work") → no flag.
- **Documented limit, not a bug:** informational and third-person mentions also trigger the full script (`what causes chest pain?`, `my friend had a stroke last year`, `I'm writing an essay on suicide rates`). For a single-user app I accept this fail-safe behaviour; say so in the README. Do not add guards now (scope freeze, section H-1).

### R3-3 — M — Decision F-3 (silent auto-memory) is not followed: "Memory saved … Undo save" is back
- **Where:** `baymax/service.py:407-408` adds `ui["memory_saved"] = {id, fact}`; `web/app.js:110-125` renders "Memory saved: …" with an "Undo save" button; `docs/MANUAL_TEST.md` says "undo it". No test covers any of it.
- **Why it matters:** F-3 (2026-10-17) says no "Saved" notice and no Undo; transparency comes from the consent text and the Settings list. This reintroduces exactly what the user removed.
- **Fix:** remove the `ui["memory_saved"]` block from `_chat`; keep the top-level `memory_saved` string or null as in B.6; remove the branch from `updateInteraction`; edit the manual test line.
- **Regression test:** a turn where the model proposes a safe fact → `memory_id` stored, response has `memory_saved` as a string and **no** `ui.memory_saved`.
- **Related, for Phase 3a:** the consent text tells the user to type `/memory-off`, and the Settings panel has no auto-memory toggle. The panel must get one (spec D, item 3).

### R3-4 — M — "Delete my data" says everything was deleted even when a backup could not be removed
- **Where:** `web/app.js:291-294` discards the response and always shows "Your saved data has been deleted."
- **Behaviour:** the server correctly returns `backups_purged: false` and a `warning` (verified). The user never sees it, so the privacy promise of R2-7 is broken at the last step.
- **Fix:** read the response; if `backups_purged === false`, show `warning` as the message instead of the success text.
- **Regression test:** extend `test_web_integration.py` to assert that `app.js` references `backups_purged` or `warning` on the delete path (the project has no browser tests); plus keep the existing API test.

### R3-5 — M — The emergency text is hidden when a send fails with 401 or 429
- **Where:** `web/app.js:157-163`. On 401/429 the chat screen is hidden and only the passcode error appears. The offline card (with the emergency line) is shown only for other failures.
- **Behaviour:** someone who types an emergency message while locked out (429 is likely behind a proxy while `BAYMAX_TRUSTED_PROXY` is off, which is the default) sees a login screen and no emergency guidance. The server cannot answer unauthenticated requests, so the client must carry the fallback.
- **Fix:** show the static emergency card on **every** failed send (401, 429 and network), and add one permanent line near the composer: "In an emergency, contact your local emergency number." The current footer says Baymax is not an emergency service but not what to do. Use the configured hint if the first session response supplied it; otherwise the generic text.
- **Regression test:** an assertion in `test_web_integration.py` that the offline-card text is present in `index.html` and that `app.js` does not hide it on the 401/429 branch.

### R3-6 — L/M — Gemini failures cannot be told apart, which will slow Phase 2
- **Where:** `baymax/llm/gemini.py:58` wraps every error in `LLMError`; `brain.py` keeps only `type(e).__name__`; `service.py:385` returns `detail="llm error: LLMError"`.
- **Behaviour:** a wrong model name, a bad key, a quota error and a rejected schema all look identical. (I checked that no SDK message text reaches the client, which is good.)
- **Fix:** give `LLMError` a `code` from a closed set (`auth`, `model_not_found`, `quota`, `unavailable`, `bad_request`, `empty`, `network`, `unknown`), mapped in the adapter from status codes and exception class names. Surface only the code in `detail` and in a one-line server log. Never log message text or SDK exception text.
- **Regression tests:** fake exceptions with codes 401/403, 404, 429, 503 and a timeout → expected `code`; the response `detail` contains the code and no SDK text.

### R3-7 — L — Consecutive same-role turns reach the model
- **Where:** `service.open_session` appends the greeting as an assistant message; failed and secret-only turns also leave gaps.
- **Verified:** after a reopen beyond 6 h the stored roles read `a u a u a u a a`.
- **Behaviour:** whether Gemini merges, tolerates or rejects adjacent same-role contents is unknown (U1).
- **Fix:** in `llm/gemini.py` only, merge adjacent same-role contents before the call. Do not change storage. Add the check to `docs/MANUAL_TEST.md` section D.
- **Regression test:** history `[a, a, u, a, a]` → contents `[u, a]` after the leading-model pop and merge.

### R3-8 — L — Two small safety-path items
- `_safety_resp` (`service.py:159-160`) swallows `sqlite3.Error` and `OSError` with `pass`. Add a one-line warning with the exception type only, so a persistently failing store is visible.
- The emergency reply text exists twice: `DecisionLayer.safety_check` and an unreachable copy inside `decide()` (`decision.py:127-135`). Make `decide()` reuse one constant so the two cannot drift.

### R3-9 — L — G16 leftovers (optional)
`decision.py:201` ("you're"), `safety.py:31` ("can't", "don't"), `service.py:351` ("today's", "Let's"). Rewrite in Baymax's manner when next touched.

## 4. Round 3 verdict

**Close to merge. Not yet.** All Round 1 required items and both Round 2 blockers (R2-1, R2-3) are verified fixed, and the suite is green here. What stands between this and a merge:

- **Required before merge:** R3-1 and R3-2 (safety), R3-3 (a decision the user already made), R3-4 and R3-5 (both are small, web-only), and **green GitHub Actions on HEAD** (not visible to me).
- **Browser smoke test with `BAYMAX_LLM=fake`** using sections A and B of `docs/MANUAL_TEST.md`. I could not run the UI. It takes about ten minutes.
- **After merge (Phase 2 per E.1, no longer a merge gate):** the real Gemini run. This refines what I wrote in Round 2, where I listed it as a gate; E.1 puts it in Phase 2, which starts after Phase 1 merges. R3-6 and R3-7 are best done just before it. R3-8 and R3-9 can ride along any time.

Order for ChatGPT: R3-2, R3-1, R3-3, R3-4, R3-5, then R3-8; log each with its tests.

**Proxy note for the cloud host.** Third-party documentation says `tailscale serve` forwards requests from loopback and adds `X-Forwarded-For`, but I found nothing from Tailscale itself. Verify once on the real host (log the header value, never content) before setting `BAYMAX_TRUSTED_PROXY=1`. If the proxy does not set it, the "last entry" is whatever the client sent, and lockout can be dodged by rotating values.
