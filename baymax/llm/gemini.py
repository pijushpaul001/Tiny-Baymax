"""Gemini adapter - the ONLY file that imports google-genai."""
import time

from .base import LLMError, classify_llm_error


def build_gemini_messages(history, user_msg):
    """Build Gemini's alternating user/model history without importing the SDK.

    Consecutive messages with the same role are joined with a blank line. Leading
    assistant messages are dropped, and the current user message is always last.
    """
    messages = []
    for item in history:
        role = "user" if item["role"] == "user" else "model"
        content = item["content"]
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + content
        else:
            messages.append({"role": role, "content": content})

    while messages and messages[0]["role"] == "model":
        messages.pop(0)

    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + user_msg
    else:
        messages.append({"role": "user", "content": user_msg})
    return messages


class GeminiAdapter:
    def __init__(self, api_key: str, model: str, fallback_model: str = None):
        if not api_key:
            raise LLMError("Gemini is not configured.", code="auth")
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
        messages = build_gemini_messages(history, user_msg)
        contents = [t.Content(role=item["role"],
                              parts=[t.Part.from_text(text=item["content"])]) for item in messages]
        config = t.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                         response_schema=schema, temperature=0.75, max_output_tokens=700)
        try:
            resp = self._call(contents, config)
        except Exception as e:
            raise LLMError("Gemini request failed.", code=classify_llm_error(e),
                           exception_type=type(e).__name__) from e
        if self._response_blocked(resp):
            raise LLMError("Gemini response blocked.", code="blocked")
        raw = (resp.text or "").strip()
        if not raw:
            raise LLMError("Gemini returned an empty response.", code="empty")
        return raw

    @staticmethod
    def _response_blocked(resp) -> bool:
        """Detect safety-filtered responses using response metadata only."""
        feedback = getattr(resp, "prompt_feedback", None)
        reason = getattr(feedback, "block_reason", None) if feedback is not None else None
        if reason is not None and str(reason).split(".")[-1].upper() not in {
            "", "NONE", "UNSPECIFIED", "BLOCK_REASON_UNSPECIFIED"
        }:
            return True
        for candidate in getattr(resp, "candidates", None) or []:
            reason = getattr(candidate, "finish_reason", None)
            if reason is not None and str(reason).split(".")[-1].upper() in {
                "SAFETY", "BLOCKED", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"
            }:
                return True
        return False
