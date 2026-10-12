# Tiny Baymax

A personal healthcare companion prototype built in Python / Google Colab, with an online language-model adapter and persistent memory. This is a supportive software project, not a substitute for a licensed healthcare professional or emergency services.

## Collaboration workflow

1. **Claude** reviews the current source and fills out [`CLAUDE_HANDOFF.md`](CLAUDE_HANDOFF.md) with the v0.6 architecture.
2. **ChatGPT** implements the approved architecture and records changes, tests, limitations, and next steps in [`IMPLEMENTATION_LOG.md`](IMPLEMENTATION_LOG.md).
3. **Claude** reviews the implementation against the handoff specification. Any architectural changes should be recorded in the handoff, with corresponding log entries.

## Current state

The repository began empty. The reported current prototype is v0.5.1, but its source notebook/code must be committed before anyone can perform a code-level audit or safely implement a migration.

## Important safety and privacy rules

- Never commit real API keys, access tokens, private health conversations, or other secrets.
- Use Colab Secrets or environment variables for credentials.
- Make memory collection transparent and give the user control to inspect and delete saved data.
- The app must clearly distinguish supportive information from professional medical care and handle urgent situations conservatively.

## Next step

Add the current v0.5.1 Colab notebook and any required source/configuration files. Replace secrets with placeholders before committing. Then ask Claude to review the source and complete `CLAUDE_HANDOFF.md`.
