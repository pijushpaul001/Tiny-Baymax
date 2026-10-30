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


    def test_previous_summaries_are_in_next_session_prompt(self):
        llm = FakeLLM()
        self.store.add_summary("u1", 1, 9, "We discussed hiking and cooking.")
        service = ChatService(self.store, llm)
        service.open_session("u1")
        service.handle("u1", "Tell me something.")
        prompt = llm.calls[-1][0]
        self.assertIn("PREVIOUS CONVERSATIONS (topic summaries, oldest first)", prompt)
        self.assertIn("We discussed hiking and cooking.", prompt)
        self.assertIn("summaries, not exact quotes", prompt)
        self.assertIn("Never claim details beyond what they contain", prompt)


    def test_recall_search_finds_old_honey_message_with_date(self):
        llm = FakeLLM()
        self.store.add_messages("u1", [("user", "We talked about honey in tea last time.")])
        service = ChatService(self.store, llm)
        service.handle("u1", "Do you remember honey?")
        prompt = llm.calls[-1][0]
        self.assertIn("OLD MESSAGES MATCHING THE QUESTION", prompt)
        self.assertIn("honey in tea", prompt)
        self.assertIn(self.store.last_message("u1")["ts"][:10], prompt)

    def test_recall_without_match_tells_model_not_to_claim_recall(self):
        llm = FakeLLM()
        service = ChatService(self.store, llm)
        service.handle("u1", "What did we talk about honey?")
        self.assertIn("No older messages match; say you do not see it.", llm.calls[-1][0])

    def test_user_cannot_recall_another_users_messages_or_summaries(self):
        llm = FakeLLM()
        self.store.add_messages("user-b", [("user", "We talked about honey from a secret api key.")])
        self.store.add_summary("user-b", 1, 2, "User B likes honey.")
        service = ChatService(self.store, llm)
        service.handle("user-a", "Do you remember honey?")
        prompt = llm.calls[-1][0]
        self.assertIn("No older messages match; say you do not see it.", prompt)
        self.assertNotIn("User B likes honey", prompt)
        self.assertNotIn("secret api key", prompt)

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
