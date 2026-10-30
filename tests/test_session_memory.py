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


    def test_six_hour_gap_ends_old_session_and_summarizes_on_next_open(self):
        from datetime import datetime, timedelta

        llm = FakeLLM(replies=["A calm reply."] * 4 + [GOOD])
        service = self._session_with_four_messages(llm)
        old_start = service.session("u1").start_message_id
        old_ts = (datetime.now() - timedelta(hours=6)).isoformat(timespec="seconds")
        self.store.db.execute(
            "UPDATE messages SET ts=? WHERE user_id=? AND id=(SELECT MAX(id) FROM messages WHERE user_id=?)",
            (old_ts, "u1", "u1"),
        )
        self.store.db.commit()
        service.open_session("u1")
        self.assertEqual(len(self.store.summaries("u1")), 1)
        self.assertNotEqual(service.session("u1").start_message_id, old_start)
        self.assertFalse(service.session("u1").ended)

    def test_shutdown_ritual_completion_marks_session_ended(self):
        service = ChatService(self.store, FakeLLM())
        service.open_session("u1")
        service.handle("u1", "/quit")
        result = service.handle("u1", "yes")
        self.assertTrue(result["ended"])
        self.assertTrue(service.session("u1").ended)

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

    def test_new_session_after_ritual_starts_a_distinct_message_range(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + [GOOD] + ["A new reply."] * 4 + [GOOD])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        first = self.store.summaries("u1")[0]
        service.open_session("u1")
        self.assertGreater(service.session("u1").start_message_id, first["last_msg_id"])
        for message in ("I like cycling.", "I enjoy baking.", "I collect books.", "What music is popular?"):
            service.handle("u1", message)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        summaries = self.store.summaries("u1", 5)
        self.assertEqual(len(summaries), 2)
        self.assertGreater(summaries[1]["first_msg_id"], summaries[0]["last_msg_id"])

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

    def test_difficulty_message_and_immediate_assistant_reply_are_removed_from_summary_input(self):
        llm = FakeLLM(replies=[GOOD])
        service = ChatService(self.store, llm)
        pairs = [
            ("assistant", "Hello."),
            ("user", "I like hiking."),
            ("assistant", "That sounds enjoyable."),
            ("user", "My head hurts."),
            ("assistant", "How would you rate the pain from 0 to 10?"),
            ("user", "I enjoy cooking."),
            ("assistant", "Cooking can be a nice hobby."),
            ("user", "I am learning guitar."),
            ("assistant", "That is an interesting skill."),
            ("user", "What books are popular?"),
            ("assistant", "There are many options."),
        ]
        ids = self.store.add_messages("u1", pairs)
        session = service.session("u1")
        session.start_message_id = ids[0]
        self.assertTrue(service._summarize_session("u1", session))
        transcript = llm.calls[0][2]
        self.assertNotIn("My head hurts", transcript)
        self.assertNotIn("How would you rate the pain", transcript)
        self.assertIn("I enjoy cooking", transcript)

    def test_health_or_mood_word_summary_is_rejected(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + ["We discussed hiking. The user mentioned sadness."])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        self.assertEqual(self.store.summaries("u1"), [])


    def test_previous_summaries_are_in_next_session_prompt(self):
        llm = FakeLLM(replies=["A calm reply."] * 4 + [GOOD, "A new-session reply."])
        service = self._session_with_four_messages(llm)
        service.handle("u1", "/quit")
        service.handle("u1", "yes")
        self.assertEqual(len(self.store.summaries("u1")), 1)
        service.open_session("u1")
        service.handle("u1", "Tell me something new.")
        prompt = llm.calls[-1][0]
        self.assertIn("PREVIOUS CONVERSATIONS (topic summaries, oldest first)", prompt)
        self.assertIn(GOOD, prompt)
        self.assertIn("summaries, not exact quotes", prompt)
        self.assertIn("Never claim details beyond what they contain", prompt)

    def test_prompt_uses_ten_relevant_plus_ten_newest_memory_facts(self):
        llm = FakeLLM()
        for index in range(15):
            fact = "honey tea preference fact 0" if index == 0 else f"honey preference fact {index}"
            self.store.add_memory("u1", fact)
        for index in range(15):
            self.store.add_memory("u1", f"recent unrelated hobby fact {index}")
        service = ChatService(self.store, llm)
        service.handle("u1", "Tell me about honey tea.")
        prompt = llm.calls[-1][0]
        facts = [line for line in prompt.splitlines() if line.startswith("- ") and
                 ("honey preference fact" in line or "recent unrelated hobby fact" in line)]
        self.assertEqual(len(facts), 20)
        self.assertTrue(any("honey tea preference fact 0" in line for line in facts))
        self.assertTrue(any("recent unrelated hobby fact 14" in line for line in facts))
        self.assertNotIn("recent unrelated hobby fact 0", prompt)

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
