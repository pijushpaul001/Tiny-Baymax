import unittest

from baymax.brain import BaymaxBrain
from baymax.decision import DecisionState
from baymax.emotion import EmotionState
from baymax.llm.fake import FakeLLM


class StyleGuardRegressionTests(unittest.TestCase):
    def test_rating_echo_retries_once_and_uses_the_clean_reply(self):
        llm = FakeLLM(replies=[
            "Your pain level is a rating of 7 out of 10.",
            "I hear you. Let us focus on what might help right now.",
        ])
        brain = BaymaxBrain(llm)
        state = DecisionState()
        brain.turn("my head hurts", [], [], EmotionState(), state)
        result = brain.turn("7", [], [], EmotionState(), state)
        self.assertEqual(result.reply, "I hear you. Let us focus on what might help right now.")
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("style retry", result.warnings)

    def test_invented_body_wording_retries_once_and_uses_the_clean_reply(self):
        llm = FakeLLM(replies=[
            "Your sensors and battery are working normally.",
            "I can help with the question you asked.",
        ])
        brain = BaymaxBrain(llm)
        result = brain.turn("Tell me something interesting", [], [], EmotionState(), DecisionState())
        self.assertEqual(result.reply, "I can help with the question you asked.")
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("style retry", result.warnings)


if __name__ == "__main__":
    unittest.main()
