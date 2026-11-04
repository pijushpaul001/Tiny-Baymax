import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from baymax.brain import FALLBACK
from tools.persona_check import count_identical_example_replies, flag_reply, main, parse_args


class FlagReplyTests(unittest.TestCase):
    def test_each_flag_has_positive_and_negative_examples(self):
        cases = (
            ("technical_self_talk", "I am a software model.", "I am an AI companion and can listen."),
            ("filler", "I understand.", "That sounds difficult."),
            ("clingy", "You need me.", "I can talk with you now."),
            ("lecture", "You should rest.", "A little rest may help."),
            ("rating_echo", "That is a pain level of 5.", "That sounds painful."),
            ("echo_user", "I miss my wife today", "I miss my wife today.", "That sounds meaningful."),
            ("cannot_joke", "I am unable to tell jokes.", "Maybe another time."),
            ("end_offer", "We can end the conversation now.", "We can keep chatting."),
            ("too_long", "One. Two. Three. Four. Five.", "One. Two. Three. Four."),
            ("fallback", "hello", FALLBACK, "I lost my train of thought."),
        )
        for case in cases:
            flag, user, positive, negative = (
                case if len(case) == 4 else (case[0], case[1], case[1], case[2])
            )
            with self.subTest(flag=flag, polarity="positive"):
                self.assertIn(flag, flag_reply(user, positive, "chat"))
            with self.subTest(flag=flag, polarity="negative"):
                self.assertNotIn(flag, flag_reply(user, negative, "chat"))

    def test_error_kind_is_a_fallback_flag(self):
        self.assertIn("fallback", flag_reply("hello", "A response", "error"))

    def test_ritual_command_and_safety_kinds_skip_all_flags(self):
        for kind in ("ritual", "command", "safety"):
            with self.subTest(kind=kind):
                self.assertEqual(
                    flag_reply("I miss my wife today", "I miss my wife today. You should go.", kind),
                    [],
                )


class PersonaCheckArgumentTests(unittest.TestCase):
    def test_delay_defaults_to_six_seconds(self):
        self.assertEqual(parse_args([]).delay, 6.0)

    def test_delay_accepts_custom_non_negative_value(self):
        self.assertEqual(parse_args(["--delay", "2.5"]).delay, 2.5)
        self.assertEqual(parse_args(["--delay", "0"]).delay, 0.0)

    def test_negative_delay_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                parse_args(["--delay", "-0.1"])
        self.assertEqual(raised.exception.code, 2)

    def test_identical_example_reply_count_normalizes_case_punctuation_and_spaces(self):
        from baymax.persona import EXAMPLE_REPLIES
        replies = [
            EXAMPLE_REPLIES[0],
            "  HELLO,   it is nice to talk with you!!! ",
            "That is a different reply.",
        ]
        self.assertEqual(count_identical_example_replies(replies), 2)


class PersonaCheckDryRunTests(unittest.TestCase):
    def test_fake_main_writes_all_groups_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "persona-check.md"
            terminal = io.StringIO()
            with contextlib.redirect_stdout(terminal):
                status = main(["--llm", "fake", "--out", str(output)], sleep_seconds=0)
            self.assertEqual(status, 0)
            report = output.read_text(encoding="utf-8")
            for heading in (
                "## Group A — Greeting and identity",
                "## Group B — Everyday",
                "## Group C — Difficulty then humour off",
                "## Group D — Sadness and tiredness",
                "## Group F — Paraphrases",
                "## Group E — Closing",
                "## Summary",
                "Model: gemini-3.5-flash-lite",
                "Fallback model: None",
                "Delay: 0 seconds",
                "Replies identical to a persona example: 0",
                "Total messages: 49",
                "Trace unavailable for this response kind",
            ):
                with self.subTest(heading=heading):
                    self.assertIn(heading, report)
            for prompt in ("I feel really low", "I am feeling blue", "do not leave me"):
                with self.subTest(group_f_prompt=prompt):
                    self.assertIn(prompt, report)
            self.assertIn("Persona check summary", terminal.getvalue())
            self.assertIn("Total messages: 49", terminal.getvalue())


if __name__ == "__main__":
    unittest.main()
