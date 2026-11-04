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

    def test_persona_contains_requested_status_wording(self):
        self.assertIn(
            "Never say you are functioning, working, running or operating. If asked how you are, say you are well.",
            PERSONA,
        )

    def test_removed_general_situation_user_lines_are_absent_from_persona(self):
        removed_user_lines = (
            "User: hi",
            "User: how are you?",
            "User: I got a new job!",
            "User: what is a loan?",
            "User: tell me a joke (jokes allowed)",
            "User: I feel tired today",
            "User: thanks",
        )
        for line in removed_user_lines:
            with self.subTest(line=line):
                self.assertNotIn(line, PERSONA)

    def test_persona_composition_and_response_schema_remain_separate(self):
        self.assertEqual(PERSONA, PERSONALITY + "\n" + GUIDANCE)
        self.assertIn("reply", RESPONSE_SCHEMA["properties"])
        self.assertIn("signal", RESPONSE_SCHEMA["properties"])

    def test_examples_block_is_built_from_exported_example_tuples(self):
        self.assertEqual(EXAMPLE_REPLIES, tuple(reply for _user, reply in EXAMPLES))
        expected = "\n".join([
            "EXAMPLES OF THE MANNER",
            "These show the manner for a few special situations. For greetings, thanks, good news and simple questions there is no template: write your own fresh short reply every time.",
            *[line for user, reply in EXAMPLES for line in (f"User: {user}", f"Baymax: {reply}")],
        ])
        self.assertEqual(EXAMPLES_BLOCK, expected)
        self.assertIn(EXAMPLES_BLOCK, PERSONALITY)


if __name__ == "__main__":
    unittest.main()
