"""Tiny Baymax - a private personal AI companion.

Layers (each only talks to the one below it):
    server/             HTTP API + static web app
    baymax/service.py   ChatService: commands, shutdown ritual, per-user sessions
    baymax/brain.py     BaymaxBrain: decision layer -> LLM -> validation
    baymax/decision.py  deterministic decision layer (no LLM, no I/O)
    baymax/llm/         swappable language models (Gemini, fake for tests)
    baymax/storage.py   SQLite persistence
"""
__version__ = "0.6.1"
