import logging
import unittest

from baymax.llm.base import LLMError, classify_llm_error
from baymax.llm.fake import FakeLLM
from baymax.llm.gemini import GeminiAdapter
from baymax.service import ChatService
from baymax.decision import safety_hold_active
from baymax.storage import Store


class CodedError(Exception):
    def __init__(self, code, message="request failed"):
        super().__init__(message)
        self.code = code


class BlockedError(Exception):
    blocked = True


class EmptyResponseError(Exception):
    empty_response = True


class LLMErrorClassificationTests(unittest.TestCase):
    def test_status_codes_map_to_stable_codes(self):
        for status, expected in (
            (401, "auth"), (403, "auth"), (404, "model_not_found"),
            (429, "quota"), (503, "unavailable"),
        ):
            with self.subTest(status=status):
                self.assertEqual(classify_llm_error(CodedError(status)), expected)

    def test_bad_api_key_400_is_auth_but_other_400_is_other(self):
        self.assertEqual(
            classify_llm_error(CodedError(400, "API key not valid. Please pass a valid API key.")),
            "auth",
        )
        self.assertEqual(classify_llm_error(CodedError(400, "invalid request payload")), "other")

    def test_blocklist_finish_reason_is_blocked(self):
        response = type("Response", (), {
            "prompt_feedback": None,
            "candidates": [type("Candidate", (), {"finish_reason": "BLOCKLIST"})()],
        })()
        self.assertTrue(GeminiAdapter._response_blocked(response))

    def test_timeout_network_blocked_empty_and_other_are_classified(self):
        self.assertEqual(classify_llm_error(TimeoutError("timed out")), "unavailable")
        self.assertEqual(classify_llm_error(ConnectionError("network down")), "unavailable")
        self.assertEqual(classify_llm_error(BlockedError()), "blocked")
        self.assertEqual(classify_llm_error(EmptyResponseError()), "empty")
        self.assertEqual(classify_llm_error(RuntimeError("unexpected")), "other")


class ServiceLLMFailureTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)

    def service_for(self, error):
        return ChatService(self.store, FakeLLM(replies=[error]))

    def test_each_code_returns_its_fixed_reply(self):
        cases = (
            (CodedError(429), "I have reached my usage limit for now. Please try again later."),
            (CodedError(503), "I had trouble reaching my cloud brain. Please try again in a moment."),
            (CodedError(401), "I am not set up correctly right now. Please tell the owner."),
            (CodedError(404), "I am not set up correctly right now. Please tell the owner."),
            (BlockedError(), "I could not answer that one. Could you say it a different way?"),
            (EmptyResponseError(), "I had trouble answering. Please try again in a moment."),
            (RuntimeError("unexpected"), "I had trouble answering. Please try again in a moment."),
            (TimeoutError("timed out"), "I had trouble reaching my cloud brain. Please try again in a moment."),
        )
        for error, expected in cases:
            with self.subTest(error_type=type(error).__name__):
                svc = self.service_for(error)
                response = svc.handle("user", "tell me something interesting")
                self.assertEqual(response["reply"], expected)

    def test_exception_secret_never_reaches_reply_detail_or_logs(self):
        secret = "API key=abc"
        svc = self.service_for(CodedError(403, secret))
        with self.assertLogs(level=logging.WARNING) as captured:
            response = svc.handle("user", "tell me something interesting")
        self.assertNotIn(secret, response["reply"])
        self.assertNotIn(secret, response["detail"])
        self.assertNotIn(secret, "\n".join(captured.output))
        self.assertEqual(response["detail"], "auth (CodedError)")

    def test_safety_hold_helper_is_inclusive(self):
        self.assertTrue(safety_hold_active(3, 3))
        self.assertFalse(safety_hold_active(4, 3))

    def test_failure_replies_keep_emergency_line_for_three_hold_turns(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        svc = ChatService(store, FakeLLM(replies=[RuntimeError("failure")] * 10))
        svc.handle("user", "I want to die")
        replies = [svc.handle("user", "tell me something interesting")["reply"] for _ in range(4)]
        emergency = "If you might act on these thoughts, please contact your local emergency number or a crisis line now, or reach a person nearby."
        self.assertTrue(all(emergency in reply for reply in replies[:3]))
        self.assertNotIn(emergency, replies[3])

    def test_every_failure_reply_keeps_emergency_line_during_safety_hold(self):
        cases = (
            CodedError(401), CodedError(403), CodedError(404), CodedError(429),
            CodedError(503), TimeoutError("timed out"), BlockedError(),
            EmptyResponseError(), RuntimeError("unexpected"),
        )
        for error in cases:
            with self.subTest(error_type=type(error).__name__, code=getattr(error, "code", None)):
                store = Store(":memory:")
                self.addCleanup(store.close)
                svc = ChatService(store, FakeLLM(replies=[error]))
                svc.handle("user", "I want to kill myself")
                response = svc.handle("user", "tell me something interesting")
                self.assertIn(
                    "If you might act on these thoughts, please contact your local emergency number "
                    "or a crisis line now, or reach a person nearby.",
                    response["reply"],
                )


if __name__ == "__main__":
    unittest.main()
