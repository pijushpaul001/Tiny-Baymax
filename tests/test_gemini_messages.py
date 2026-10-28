import unittest

from baymax.llm.gemini import build_gemini_messages


class GeminiMessageBuilderTests(unittest.TestCase):
    def test_leading_assistant_messages_are_dropped(self):
        messages = build_gemini_messages([
            {"role": "assistant", "content": "old answer"},
            {"role": "assistant", "content": "another old answer"},
            {"role": "user", "content": "current context"},
        ], "new question")
        self.assertEqual(messages, [
            {"role": "user", "content": "current context\n\nnew question"},
        ])

    def test_consecutive_users_merge_and_roles_alternate(self):
        messages = build_gemini_messages([
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "answer"},
        ], "follow-up")
        self.assertEqual(messages, [
            {"role": "user", "content": "first\n\nsecond"},
            {"role": "model", "content": "answer"},
            {"role": "user", "content": "follow-up"},
        ])
        self.assertTrue(all(a["role"] != b["role"] for a, b in zip(messages, messages[1:])))
        self.assertEqual(messages[-1]["role"], "user")

    def test_new_user_message_merges_with_history_ending_in_user(self):
        messages = build_gemini_messages([
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "last history message"},
        ], "new message")
        self.assertEqual(messages[-1], {
            "role": "user", "content": "last history message\n\nnew message"
        })
        self.assertTrue(all(a["role"] != b["role"] for a, b in zip(messages, messages[1:])))

    def test_empty_history_contains_only_new_user_message(self):
        self.assertEqual(build_gemini_messages([], "new message"), [
            {"role": "user", "content": "new message"},
        ])


if __name__ == "__main__":
    unittest.main()
