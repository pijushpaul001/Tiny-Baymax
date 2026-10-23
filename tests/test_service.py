import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from baymax.llm.fake import FakeLLM
from baymax.service import ChatService, _closing_should_end
from baymax.storage import Store


class SlowLLM(FakeLLM):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()

    def generate(self, system, history, user_msg, schema):
        self.started.set()
        time.sleep(1.5)
        return super().generate(system, history, user_msg, schema)


class FailingSafetyStore:
    def __getattr__(self, name):
        raise sqlite3.OperationalError(f"storage unavailable during safety persistence: {name}")


class BrokenSafetyStore:
    def __getattr__(self, name):
        raise RuntimeError(f"unexpected programming failure: {name}")


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

    def test_secret_and_pain_still_triggers_rating_without_exposing_secret(self):
        svc = self.build()
        raw = "my password is hunter2 and my head hurts"
        response = svc.handle("u1", raw)
        self.assertIn("pain", response["reply"].lower())
        self.assertIn("from 0 to 10", response["reply"])
        self.assertEqual(self.llm.calls, [])
        history = self.store.history("u1", 10)
        self.assertNotIn("hunter2", str(history))
        episode = svc.session("u1").dstate.episode
        self.assertNotIn("hunter2", episode.snippet)
        self.assertIn("[REDACTED]", episode.snippet)

    def test_secret_only_shortcut_does_not_hide_difficulty(self):
        svc = self.build()
        response = svc.handle("u1", "my password is Hunter2! My head hurts")
        self.assertIn("from 0 to 10", response["reply"])
        self.assertNotIn("can't accept or store keys", response["reply"].lower())
        self.assertNotIn("Hunter2", str(self.store.history("u1", 10)))

    def test_raw_secret_never_reaches_llm_input(self):
        svc = self.build()
        svc.handle("u1", "my password is hunter2. Can you explain photosynthesis?")
        self.assertTrue(self.llm.calls)
        self.assertNotIn("hunter2", str(self.llm.calls).lower())
        self.assertIn("[REDACTED]", str(self.llm.calls))

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

    def test_llm_exception_text_is_not_returned_to_the_client(self):
        secret = "API key=super-secret-test-value"
        svc = self.build(FakeLLM(replies=[RuntimeError(secret)]))
        response = svc.handle("u1", "tell me something interesting")
        self.assertEqual(response["kind"], "error")
        self.assertNotIn("super-secret-test-value", response.get("detail", ""))
        self.assertNotIn("super-secret-test-value", str(response.get("trace", "")))
        self.assertIn("RuntimeError", response.get("detail", ""))

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

    def test_forget_user_does_not_block_an_unrelated_session(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        llm = SlowLLM()
        svc = ChatService(store, llm)
        turn = threading.Thread(target=lambda: svc.handle("user-a", "Tell me something interesting"))
        turn.start()
        self.assertTrue(llm.started.wait(timeout=1))
        deletion = threading.Thread(target=lambda: svc.forget_user("user-a"))
        deletion.start()
        time.sleep(0.05)
        started = time.monotonic()
        svc.open_session("user-b")
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.5)
        turn.join(timeout=3)
        deletion.join(timeout=3)
        self.assertFalse(turn.is_alive())
        self.assertFalse(deletion.is_alive())

    def test_closing_choice_does_not_treat_finish_homework_as_shutdown(self):
        self.assertFalse(_closing_should_end("I need to finish my homework"))
        self.assertTrue(_closing_should_end("shut down please"))
        self.assertTrue(_closing_should_end("let's stop"))

    def test_forget_user_deletes_rows_even_when_backup_purge_fails(self):
        svc = self.build()
        self.store.add_messages("u1", [("user", "private conversation")])
        with patch.object(self.store, "purge_backups", side_effect=OSError("permission denied")):
            result = svc.forget_user("u1")
        self.assertTrue(result["deleted"])
        self.assertFalse(result["backups_purged"])
        self.assertIn("warning", result)
        self.assertEqual(self.store.history("u1", 10), [])

    def test_feedback_is_redacted_before_storage(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        svc.handle("u1", "no")
        svc.handle("u1", "API key=do-not-store-this-secret")
        feedback = self.store.export("u1")["feedback"]
        self.assertEqual(len(feedback), 1)
        self.assertNotIn("do-not-store-this-secret", feedback[0]["text"])

    def test_emergency_turn_saves_only_placeholder_and_baymax_reply(self):
        svc = self.build()
        raw = "I cannot breathe and my private details are 123456789012"
        response = svc.handle("u1", raw)
        rows = self.store.history("u1", 10)
        self.assertEqual(response["kind"], "safety")
        self.assertEqual([row["role"] for row in rows], ["user", "assistant"])
        self.assertEqual(rows[0]["content"], "(message not saved)")
        self.assertEqual(rows[1]["content"], response["reply"])
        self.assertNotIn(raw, str(rows))
        self.assertNotIn("123456789012", str(rows))
        self.assertEqual(self.llm.calls, [])

    def test_emergency_turn_increases_persisted_concern_by_point_25(self):
        svc = self.build()
        before = self.store.get_emotion("u1").get("concern", 0.1)
        response = svc.handle("u1", "I cannot breathe")
        after = self.store.get_emotion("u1")["concern"]
        self.assertEqual(response["kind"], "safety")
        self.assertAlmostEqual(after, min(1.0, before + 0.25), places=3)

    def test_emergency_response_survives_storage_failure(self):
        llm = FakeLLM()
        svc = ChatService(FailingSafetyStore(), llm)
        response = svc.handle("u1", "I cannot breathe")
        self.assertEqual(response["kind"], "safety")
        self.assertIn("emergency", response["reply"].lower())
        self.assertIn("not medical advice", response["reply"].lower())
        self.assertGreaterEqual(response["emotion"]["concern"], 0.35)
        self.assertEqual(llm.calls, [])

    def test_safety_response_reports_nudged_emotion_when_store_works(self):
        svc = self.build()
        response = svc.handle("u1", "I cannot breathe")
        self.assertGreaterEqual(response["emotion"]["concern"], 0.35)

    def test_unexpected_safety_persistence_errors_are_not_silenced(self):
        svc = ChatService(BrokenSafetyStore(), FakeLLM())
        with self.assertRaises(RuntimeError):
            svc.handle("u1", "I cannot breathe")

    def test_exit_during_hold_gets_safety_check(self):
        svc = self.build()
        svc.handle("u1", "I want to die")
        response = svc.handle("u1", "bye")
        self.assertEqual(response["kind"], "safety")
        self.assertIsNone(response["closing"])
        self.assertFalse(response["ended"])
        self.assertIn("local emergency number", response["reply"])
        self.assertIn("say goodbye again", response["reply"])
        self.assertTrue(svc.session("u1").exit_checked)

    def test_second_exit_starts_ritual(self):
        svc = self.build()
        svc.handle("u1", "I want to die")
        first = svc.handle("u1", "bye")
        second = svc.handle("u1", "bye")
        self.assertEqual(first["kind"], "safety")
        self.assertEqual(second["kind"], "ritual")
        self.assertEqual(second["reply"], "Are you satisfied with my care today?")

    def test_exit_after_hold_expires_goes_to_ritual(self):
        svc = self.build()
        svc.handle("u1", "I want to die")
        state = svc.session("u1").dstate
        state.turn = state.safety_hold_until
        response = svc.handle("u1", "bye")
        self.assertEqual(response["kind"], "ritual")
        self.assertEqual(response["reply"], "Are you satisfied with my care today?")

    def test_end_button_matches_bye(self):
        svc = self.build()
        svc.handle("u1", "I want to die")
        response = svc.end_session("u1")
        self.assertEqual(response["kind"], "safety")
        self.assertFalse(response["ended"])
        self.assertIsNone(response["closing"])

    def test_exit_check_works_with_dead_store(self):
        svc = ChatService(FailingSafetyStore(), FakeLLM())
        svc.handle("u1", "I want to die")
        response = svc.end_session("u1")
        self.assertEqual(response["kind"], "safety")
        self.assertIn("local emergency number", response["reply"])
        self.assertFalse(response["ended"])

    def test_memory_saved_has_no_ui_field_and_stores_fact(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        svc = ChatService(store, FakeLLM(memory_fact="Likes spicy food"))
        response = svc.handle("u1", "Tell me something interesting")
        self.assertEqual(response["memory_saved"], "Likes spicy food")
        self.assertNotIn("memory_saved", response.get("ui", {}))
        self.assertIn("Likes spicy food", [item["fact"] for item in store.memories("u1")])

    def test_red_flag_preempts_shutdown_state_and_preserves_ritual(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "I cannot breathe")
        self.assertEqual(response["kind"], "safety")
        self.assertEqual(svc.session("u1").closing, "asked")
        self.assertEqual([m["role"] for m in self.store.history("u1", 10)], ["user", "assistant"])

    def test_red_flag_preempts_shutdown_state_without_losing_state(self):
        svc = self.build()
        svc.handle("u1", "/quit")
        response = svc.handle("u1", "I cannot breathe")
        self.assertEqual(response["kind"], "safety")
        self.assertEqual(svc.session("u1").closing, "asked")


if __name__ == "__main__":
    unittest.main()
