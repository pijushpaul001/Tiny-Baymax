"""The only thing the rest of Baymax knows about a language model."""
from typing import Protocol


class LLMError(RuntimeError):
    """Raised by an adapter when the model could not be reached or answered badly."""


class LLMAdapter(Protocol):
    def generate(self, system: str, history: list, user_msg: str, schema: dict) -> str:
        """Return the model's raw JSON text.

        history: list of {"role": "user"|"assistant", "content": str}, oldest first,
                 NOT including user_msg.
        """
        ...
