import unittest

from baymax.persona import GUIDANCE, PERSONALITY, PERSONA, RESPONSE_SCHEMA


class PersonaPromptTests(unittest.TestCase):
    def test_persona_uses_the_healthcare_companion_identity_and_required_sections(self):
        self.assertIn("You are Baymax, a gentle personal healthcare companion.", PERSONALITY)
        for heading in (
            "HOW BAYMAX SPEAKS", "WHAT BAYMAX IS", "CARING WITHOUT CLINGING",
            "HEALTH", "THE DECISION BRIEF", "KNOWLEDGE QUESTIONS", "MEMORY",
            "EXAMPLES OF THE MANNER",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, PERSONALITY)

    def test_persona_composition_and_response_schema_remain_separate(self):
        self.assertEqual(PERSONA, PERSONALITY + "\n" + GUIDANCE)
        self.assertIn("reply", RESPONSE_SCHEMA["properties"])
        self.assertIn("signal", RESPONSE_SCHEMA["properties"])


if __name__ == "__main__":
    unittest.main()
