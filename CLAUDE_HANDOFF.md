# Claude Architecture Handoff — Tiny Baymax

## Purpose

Claude is the architecture owner for the next iteration of Tiny Baymax. Review the existing implementation when it is supplied, design the target architecture for **v0.6**, and maintain this file as the authoritative architecture specification. ChatGPT will implement against the approved specification and maintain `IMPLEMENTATION_LOG.md`. Claude should review the implementation against the spec and identify gaps.

## Project context (reported by the user; verify against source when available)

- Project name: Tiny Baymax / Baymax.
- Current working prototype reported by the user: v0.5.1.
- Development environment: Google Colab / Python.
- Online model: Gemini API. A previously working model identifier was `gemini-3.5-flash-lite`; treat this as historical configuration, not a guaranteed current model.
- Persistent memory: Google Drive mounted in Colab, previously at `/content/gdrive`.
- State / behavior layer: Python-based decision logic and a simulated emotion-state engine.
- Goal: evolve a prototype into a maintainable, testable personal healthcare companion app. This is not a substitute for professional medical care.

## Non-negotiable product behavior

1. At startup, introduce itself as: **“Baymax, your personal healthcare companion.”**
2. When a user reports pain or sadness, request an immediate severity rating at that point in the conversation. This rating is specifically for pain/sadness, not a generic conversation score. Make the scale explicit and consistent, and allow the user to skip or correct it.
3. Before a normal shutdown, ask: **“Are you satisfied with my care today?”** Wait for the user's response before giving the closing message. Do not trap the user in an endless loop; provide a clear exit path.
4. Keep memory handling transparent and controllable. Avoid storing sensitive health details by default without an explicit, understandable consent design.
5. Keep credentials out of source control. Read API keys from environment variables or Colab Secrets; never put real keys in code, notebooks, logs, or committed example files.
6. Treat medical safety as a first-class requirement. Do not diagnose with certainty, do not imply emergency services have been contacted, and route urgent danger / emergency symptoms to appropriate local emergency support. State that this is supportive information, not professional medical advice.
7. Gracefully handle unavailable model APIs, quota/rate limits, network failures, malformed responses, and missing Drive mounts. The app should explain the issue and avoid losing existing memory.
8. Keep the user's data portable and provide a way to inspect, export, and delete stored memory.
9. Preserve working behavior unless the specification explicitly changes it. Do not silently change versions or break existing memory files.

## Architecture work requested from Claude

Please inspect the source notebook/code and current sample memory files once they are added. Then fill out this document with a specific, implementable v0.6 architecture. Do not merely provide generic recommendations.

### A. Current-state assessment
- Inventory existing modules/cells, responsibilities, data flow, external dependencies, API usage, and persistent files.
- Identify what currently works, known bugs, security risks, and unknowns.
- Separate verified observations from assumptions.

### B. Target architecture
Specify components and contracts, such as:
- user interface / conversation loop
- intent and safety triage
- pain/sadness severity capture and follow-up state
- response orchestration and Gemini adapter
- memory service and consent controls
- simulated emotion-state engine (clearly distinct from real emotion)
- satisfaction-before-shutdown flow
- configuration/secrets management
- logging, error recovery, and tests

Provide a data-flow diagram (Mermaid is welcome), module responsibilities, function/interface signatures, state model, memory schema/versioning, and error behavior. Fit the current project and user's environment instead of overengineering.

### C. Conversation/state requirements
Define how to handle at least:
- startup and introduction
- ordinary conversation
- pain disclosure and immediate severity rating
- sadness disclosure and immediate severity rating
- follow-up while waiting for a rating
- user skips/changes a rating
- user changes topic mid-flow
- user types shutdown/exit commands
- satisfaction question and response before closure
- urgent-risk language / medical emergency escalation
- failed model request or missing memory storage

### D. Privacy and safety
Document consent, data minimization, retention, user-visible memory controls, secret handling, safety boundaries, and testable requirements. Do not claim regulatory compliance without evidence.

### E. Migration and acceptance criteria
- Give a step-by-step migration from v0.5.1 to v0.6.
- Define acceptance criteria and a test plan for all non-negotiable product behavior.
- Identify any user decisions needed; make conservative assumptions explicit.
- Note which changes are required versus optional.
- Keep the design usable in Google Colab initially, while describing a sensible path to a free/low-cost app deployment without promising that third-party APIs will remain free.

## Claude output instructions

1. Replace the **Architecture status** below with a concise status (e.g. Draft / Ready for implementation / Needs user decisions).
2. Keep the project context and non-negotiable product behavior unless the source review reveals contradictions; if so, document them instead of silently deleting requirements.
3. Add the completed architecture under **Architecture specification**.
4. Add a dated entry to **Architecture change history** whenever the architecture is materially revised.
5. Do not implement code in this file. The implementation is tracked separately.
6. When finished, give the user a clear handoff note: what files were reviewed, architecture decisions, unresolved questions, and that ChatGPT should now implement and update the log.

## Architecture status

**Status: Awaiting source review.** The repository was initially empty when this handoff was created. The current v0.5.1 source notebook/code still needs to be added.

## Architecture specification

_Claude: populate this section after reviewing source._

## Architecture change history

- 2026-10-12 — Initial handoff template created. No source files were present in the repository at creation time.
