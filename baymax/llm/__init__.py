"""Swappable language models. Gemini is imported lazily in its own module."""
from .base import LLMAdapter, LLMError
from .fake import FakeLLM

__all__ = ["LLMAdapter", "LLMError", "FakeLLM"]
