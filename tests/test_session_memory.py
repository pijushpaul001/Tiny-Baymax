import unittest

from baymax.llm.fake import FakeLLM
from baymax.service import ChatService
from baymax.storage import Store


GOOD = "We discussed hiking and cooking. The user asked about learning guitar."


class SessionSummaryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)

    def _session_with_four_messages(self, llm):
        service = ChatService(self.store, llm)
        service.open_session("u1")
        for message in ("I like hiking.", "I enjoy cooking.", "I am learning guitar.", "What books are popular?"):
            service.handle("u1", message)
        return service

    def test_summary_created_once_after_shutdown_ritual(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + [GOOD])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        ended = service.handle("u1", "yes")
        self.assertTrue(ended["ended"])
        self.assertEqual(len(self.store.summaries("u1")), 1)
        self.assertEqual(len(llm.calls), 5)
        service.open_session("u1")
        self.assertEqual(len(self.store.summaries("u1")), 1)

    def test_no_summary_under_four_user_messages(self):
        llm = FakeLLM(replies=["A calm reply."] * 3)
        service = ChatService(self.store, llm)
        service.open_session("u1")
        for message in ("I like hiking.", "I enjoy cooking.", "I am learning guitar."):
            service.handle("u1", message)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        self.assertEqual(self.store.summaries("u1"), [])

    def test_secret_is_redacted_from_summary_before_storage(self):
        secret_reply = "We discussed hobbies. My password is ultra-secret-998877. We discussed music."
        llm = FakeLLM(replies=["A calm reply."] * 4 + [secret_reply])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        summaries = self.store.summaries("u1")
        self.assertEqual(len(summaries), 1)
        self.assertNotIn("ultra-secret-998877", summaries[0]["text"])

    def test_health_or_mood_word_summary_is_rejected(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + ["We discussed hiking. The user mentioned pain and sadness."])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        self.assertEqual(self.store.summaries("u1"), [])

    def test_failing_summary_llm_does_not_break_session_open_or_chat(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + [RuntimeError("private provider error")])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        ended = service.handle("u1", "yes")
        self.assertTrue(ended["ended"])
        opened = service.open_session("u1")
        self.assertIn("history", opened)
        response = service.handle("u1", "Tell me something else.")
        self.assertEqual(response["kind"], "chat")
        self.assertEqual(self.store.summaries("u1"), [])


if __name__ == "__main__":
    unittest.main()
