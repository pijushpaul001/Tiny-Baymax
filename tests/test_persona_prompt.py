import unittest

from baymax.persona import EXAMPLES, EXAMPLE_REPLIES, EXAMPLES_BLOCK, GUIDANCE, PERSONALITY, PERSONA, RESPONSE_SCHEMA


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

    def test_examples_block_is_built_from_exported_example_tuples(self):
        self.assertEqual(EXAMPLE_REPLIES, tuple(reply for _user, reply in EXAMPLES))
        expected = "\\n".join([
            "EXAMPLES OF THE MANNER",
            "These show the manner only. Never reuse an example sentence. Write a fresh reply in the same manner, even when the user says exactly what an example says.",
            *[line for user, reply in EXAMPLES for line in (f"User: {user}", f"Baymax: {reply}")],
        ])
        self.assertEqual(EXAMPLES_BLOCK, expected)
        self.assertIn(EXAMPLES_BLOCK, PERSONALITY)


if __name__ == "__main__":
    unittest.main()
