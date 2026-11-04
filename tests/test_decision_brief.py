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


if __name__ == "__main__":
    unittest.main()
