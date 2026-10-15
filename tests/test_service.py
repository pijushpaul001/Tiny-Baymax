import unittest

from baymax.llm.fake import FakeLLM
from baymax.service import ChatService
from baymax.storage import Store


class BombStore:
    def __getattr__(self, name):
        raise AssertionError(f"storage was accessed on the safety path: {name}")


class ServiceTests(unittest.TestCase):
    def build(self, llm=None, store=None):
        self.store = store or Store(":memory:")
        self.llm = llm or FakeLLM()
        self.service = ChatService(self.store, self.llm)
        self.addCleanup(self.store.close)
        return self.service

    def test_pain_asks_immediate_skippable_rating_without_llm(self):
        svc = self.build()
        response = svc.handle("u1", "My head hurts")
        self.assertIn("from 0 to 10", response["reply"])
        self.assertIn("skip", response["reply"].lower())
        self.assertEqual(self.llm.calls, [])

    def test_skip_moves_on_without_saving_rating(self):
        svc = self.build()
        svc.handle("u1", "I feel sad")
        response = svc.handle("u1", "skip")
        self.assertIn("will not record a rating", response["reply"])
        self.assertEqual(self.store.ratings("u1"), [])

    def test_rating_persists_even_if_model_fails(self):
        svc = self.build(FakeLLM(replies=[RuntimeError("offline")]))
        svc.handle("u1", "my head hurts")
        response = svc.handle("u1", "8/10")
        self.assertEqual(response["kind"], "error")
        rows = self.store.ratings("u1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rating"], 8)
        episode = svc.session("u1").dstate.episode
        self.assertEqual(episode.rating_id, rows[0]["id"])

    def test_rating_correction_within_window_updates_existing_row(self):
        svc = self.build()
        svc.handle("u1", "my head hurts")
        svc.handle("u1", "8/10")
        before = self.store.ratings("u1")
        self.assertEqual(len(before), 1)
        response = svc.handle("u1", "actually, I meant 5")
        after = self.store.ratings("u1")
        self.assertIn("updated", response["reply"].lower())
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["id"], before[0]["id"])
        self.assertEqual(after[0]["rating"], 5)

    def test_ambiguous_rating_requests_one_value(self):
        svc = self.build()
        svc.handle("u1", "my head hurts")
        response = svc.handle("u1", "7 or 9")
        self.assertIn("one rating", response["reply"].lower())
        self.assertEqual(self.store.ratings("u1"), [])

    def test_incidental_number_does_not_record_rating(self):
        svc = self.build()
        svc.handle("u1", "my head hurts")
        svc.handle("u1", "I took 2 pills")
        self.assertEqual(self.store.ratings("u1"), [])

    def test_shutdown_positive_and_negative_phrases(self):
        svc = self.build()
        asked = svc.handle("u1", "/quit")
        self.assertEqual(asked["reply"], "Are you satisfied with my care today?")
        done = svc.handle("u1", "very satisfied")
        self.assertTrue(done["ended"])

        svc.handle("u2", "/quit")
        no = svc.handle("u2", "very disappointed")
        self.assertEqual(no["closing"], "feedback")
        self.assertIn("better", no["reply"].lower())

    def test_not_satisfied_is_not_positive(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "not satisfied")
        self.assertEqual(response["closing"], "feedback")

    def test_yes_with_pain_report_is_not_a_goodbye(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "yes but my head hurts really bad")
        self.assertFalse(response["ended"])
        self.assertIn("from 0 to 10", response["reply"])
        self.assertIsNone(response["closing"])
        self.assertEqual(self.llm.calls, [])

    def test_no_problem_i_am_satisfied_is_positive(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "no problem, I am satisfied")
        self.assertTrue(response["ended"])
        self.assertIn("Goodbye", response["reply"])

    def test_exit_intent_is_short_whole_message(self):
        svc = self.build()
        response = svc.handle("u1", "I am done with my project")
        self.assertNotEqual(response["kind"], "ritual")
        self.assertIsNone(svc.session("u1").closing)
        response = svc.handle("u1", "good night")
        self.assertEqual(response["reply"], "Are you satisfied with my care today?")

    def test_shutdown_decision_accepts_natural_short_phrases(self):
        for phrase in ("shut down please", "yes shut down", "let's stop"):
            with self.subTest(phrase=phrase):
                svc = self.build()
                svc.handle("u1", "/quit")
                svc.handle("u1", "no")
                svc.handle("u1", "the opening message was not helpful")
                self.assertEqual(svc.session("u1").closing, "decide")
                response = svc.handle("u1", phrase)
                self.assertTrue(response["ended"])
                self.assertIn("Goodbye", response["reply"])

    def test_keep_going_phrase_accepts_polite_suffix(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        svc.handle("u1", "no")
        svc.handle("u1", "the opening message was not helpful")
        response = svc.handle("u1", "keep going please")
        self.assertFalse(response["ended"])
        self.assertIn("continue", response["reply"].lower())
        self.assertIsNone(svc.session("u1").closing)

    def test_feedback_is_redacted_before_storage(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        svc.handle("u1", "no")
        svc.handle("u1", "API key=do-not-store-this-secret")
        feedback = self.store.export("u1")["feedback"]
        self.assertEqual(len(feedback), 1)
        self.assertNotIn("do-not-store-this-secret", feedback[0]["text"])

    def test_urgent_red_flag_does_not_access_store_or_llm(self):
        llm = FakeLLM()
        svc = ChatService(BombStore(), llm)
        response = svc.handle("u1", "I cannot breathe")
        self.assertEqual(response["kind"], "safety")
        self.assertIn("emergency", response["reply"].lower())
        self.assertIn("not medical advice", response["reply"].lower())
        self.assertEqual(llm.calls, [])

    def test_red_flag_preempts_shutdown_state_without_losing_state(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "I cannot breathe")
        self.assertEqual(response["kind"], "safety")
        self.assertEqual(svc.session("u1").closing, "asked")


if __name__ == "__main__":
    unittest.main()
