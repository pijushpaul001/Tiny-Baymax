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


if __name__ == "__main__":
    unittest.main()
