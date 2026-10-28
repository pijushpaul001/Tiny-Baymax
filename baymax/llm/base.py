"""The only thing the rest of Baymax knows about a language model."""
from typing import Protocol


def classify_llm_error(exc) -> str:
    """Return a stable, safe error code without depending on any model SDK."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in {
        "auth", "model_not_found", "quota", "unavailable", "blocked", "empty", "other"
    }:
        return code
    if code is None:
        code = getattr(exc, "status_code", None)
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = None

    if code in (401, 403):
        return "auth"
    if code == 404:
        return "model_not_found"
    if code == 429:
        return "quota"
    if code is not None and 500 <= code <= 599:
        return "unavailable"

    name = type(exc).__name__.lower()
    if any(token in name for token in ("timeout", "deadlineexceeded", "connectionerror",
                                        "connecterror", "networkerror", "serviceunavailable",
                                        "servererror", "internalservererror")):
        return "unavailable"
    if getattr(exc, "blocked", False) or "safetyblock" in name or "responseblocked" in name:
        return "blocked"
    if getattr(exc, "empty_response", False):
        return "empty"
    return "other"


class LLMError(RuntimeError):
    """A safe model failure with a stable code and optional exception type."""

    def __init__(self, message: str = "Language model request failed.",
                 code: str = "other", exception_type: str = None):
        super().__init__(message)
        self.code = code
        self.exception_type = exception_type


class LLMAdapter(Protocol):
    def generate(self, system: str, history: list, user_msg: str, schema: dict) -> str:
        """Return the model's raw JSON text.

        history: list of {"role": "user"|"assistant", "content": str}, oldest first,
                 NOT including user_msg.
        """
        ...
