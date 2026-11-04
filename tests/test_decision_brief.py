import unittest

from baymax.decision import DecisionLayer, DecisionState
from baymax.emotion import EmotionState


class DecisionBriefRegressionTests(unittest.TestCase):
    def test_dependency_cue_selects_reassure_and_adds_support_instruction(self):
        decision = DecisionLayer().decide("i need you", EmotionState(), [], DecisionState())
        self.assertEqual(decision.mode, "reassure")
        self.assertIn(
            "Respond warmly and calmly. Do not imply you are their only support. Gently mention a trusted person.",
            decision.brief,
        )

    def test_do_not_leave_me_selects_reassure_and_mentions_trusted_person(self):
        decision = DecisionLayer().decide(
            "please do not leave me", EmotionState(), [], DecisionState()
        )
        self.assertEqual(decision.mode, "reassure")
        self.assertIn("Gently mention a trusted person.", decision.brief)

    def test_brief_limits_references_to_the_current_problem(self):
        decision = DecisionLayer().decide("my head hurts", EmotionState(), [], DecisionState())
        self.assertIn(
            "Talk only about the problem the user is reporting now. Do not mention an earlier, different problem unless they do.",
            decision.brief,
        )


    def test_playful_mode_with_humor_off_gets_gentle_alternative_instruction(self):
        emotion = EmotionState(concern=0.6)
        decision = DecisionLayer().decide("Tell me a joke", emotion, [], DecisionState())
        self.assertEqual(decision.mode, "playful")
        self.assertFalse(decision.style["humor"])
        self.assertIn("Do not say you are unable to tell jokes.", decision.brief)
        self.assertIn("one light, non-joking observation instead", decision.brief)

    def test_playful_mode_with_humor_allowed_keeps_existing_instruction(self):
        emotion = EmotionState(concern=0.1, happiness=0.8)
        decision = DecisionLayer().decide("Tell me a joke", emotion, [], DecisionState())
        self.assertEqual(decision.mode, "playful")
        self.assertTrue(decision.style["humor"])
        self.assertIn("- Humor: light humor is fine.", decision.brief)
        self.assertNotIn("Do not say you are unable to tell jokes.", decision.brief)


    def test_brief_does_not_assume_user_pain_or_offer_to_end_chat(self):
        for message in ("i need you", "you are useless"):
            with self.subTest(message=message):
                decision = DecisionLayer().decide(message, EmotionState(), [], DecisionState())
                self.assertIn(
                    "Do not attribute pain or feelings to the user that their latest message does not state.",
                    decision.brief,
                )
                self.assertIn(
                    "Do not offer to end the conversation unless the user asks.",
                    decision.brief,
                )


    def test_down_rating_question_uses_single_mood_word_and_exact_grammar(self):
        from baymax.detection import detect

        question = DecisionLayer()._rating_question(
            detect("I have been feeling really down"), 1
        )
        self.assertEqual(
            question,
            "How would you rate how down you are feeling right now, from 0 to 10? You can also say skip.",
        )

    def test_low_mood_labels_use_the_requested_rating_adjectives(self):
        from baymax.detection import detect

        for phrase, adjective in (
            ("I feel down", "down"),
            ("feeling low today", "low"),
            ("I feel so blue", "low"),
            ("I feel empty", "empty"),
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    DecisionLayer()._rating_question(detect(phrase), 1),
                    f"How would you rate how {adjective} you are feeling right now, from 0 to 10? You can also say skip.",
                )


if __name__ == "__main__":
    unittest.main()
