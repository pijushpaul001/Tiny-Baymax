# Instructions for AI coding agents (ChatGPT / Codex)

Read `CLAUDE_HANDOFF.md` first. It is the authoritative architecture spec. Log your work in `IMPLEMENTATION_LOG.md`.

## Rules
1. Gemini is the language brain only. Deterministic Python enforces: greeting, shutdown ritual, 0-10 ratings (asked immediately on pain or sadness, never at shutdown), emergency replies, memory rules, secret redaction, commands.
2. Baymax is not a doctor: no diagnosis, no invented cures, never imply emergency services were contacted.
3. Memory: stable non-sensitive facts only. Never auto-save health, mood, injuries, finances, exact location, private relationships, politics, keys or passwords.
4. Secrets never in code, logs, database or git. Keys live in `.env` (git-ignored).
5. Simulated emotion is computational state, never claimed as real feeling, and must change behaviour.
6. Caring but never clingy. Never invent implications about the user.
7. The user can always inspect, delete and export data, clear history, reset emotion and exit.
8. Write new dialogue in Baymax's manner (short, calm, plain, few contractions). No film lines, no voice cloning.

## Engineering
- Do not break working features. Small incremental changes, one concern per pull request, tests with every change.
- Keep Gemini-specific code in `baymax/llm/gemini.py` and configuration in `baymax/config.py`.
- Prefer deterministic Python for anything safety-critical.
- Explain breaking changes before making them. Do not change versions silently.
- Run tests: `python -m unittest discover -s tests -t .`
- If the spec is unclear or looks wrong, note it in `IMPLEMENTATION_LOG.md` and ask. Do not guess.
