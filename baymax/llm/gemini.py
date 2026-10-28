"""Gemini adapter - the ONLY file that imports google-genai."""
import time

from .base import LLMError


class GeminiAdapter:
    def __init__(self, api_key: str, model: str, fallback_model: str = None):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set.")
        from google import genai          # imported lazily so tests need no SDK
        from google.genai import types
        self._types = types
        self.client = genai.Client(api_key=api_key)
        self.model, self.fallback_model = model, fallback_model

    @staticmethod
    def _transient(e) -> bool:
        code = getattr(e, "code", None) or getattr(e, "status_code", None)
        return code in (429, 500, 502, 503, 504) or type(e).__name__ == "ServerError"

    def _call(self, contents, config):
        """Retry transient errors (5xx / 429) with backoff, then try the optional fallback model."""
        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        for mi, model in enumerate(models):
            for attempt in range(3):
                try:
                    return self.client.models.generate_content(model=model, contents=contents, config=config)
                except Exception as e:
                    if not self._transient(e) or (mi == len(models) - 1 and attempt == 2):
                        raise
                    if attempt < 2:
                        time.sleep(1.5 * 2 ** attempt)

    def generate(self, system, history, user_msg, schema):
        t = self._types
        contents = [t.Content(role="user" if h["role"] == "user" else "model",
                              parts=[t.Part.from_text(text=h["content"])]) for h in history]
        contents.append(t.Content(role="user", parts=[t.Part.from_text(text=user_msg)]))
        while contents and contents[0].role == "model":     # Gemini wants a user turn first
            contents.pop(0)
        config = t.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                         response_schema=schema, temperature=0.75, max_output_tokens=700)
        try:
            resp = self._call(contents, config)
        except Exception as e:
            raise LLMError(f"{type(e).__name__}: {str(e)[:200]}") from e
        raw = (resp.text or "").strip()
        if not raw:
            raise LLMError("Gemini returned an empty response.")
        return raw
