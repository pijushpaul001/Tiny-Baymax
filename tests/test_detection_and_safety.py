import unittest

from baymax.detection import parse_rating, parse_rating_reply
from baymax.safety import memory_gate, redact_secrets


class RatingParserTests(unittest.TestCase):
    def test_accepts_bare_values_and_words(self):
        self.assertEqual(parse_rating_reply("9").value, 9)
        self.assertEqual(parse_rating_reply("nine").value, 9)
        self.assertEqual(parse_rating_reply("about a six I think").value, 6)
        self.assertEqual(parse_rating_reply("my pain is 4").value, 4)
        self.assertEqual(parse_rating_reply("8 out of 10").value, 8)
        self.assertEqual(parse_rating_reply("8/10").value, 8)
        for phrase, expected in (
            ("it is about a six", 6),
            ("i'd say about a six", 6),
            ("its 7", 7),
            ("like a 7", 7),
            ("pretty bad, maybe 7", 7),
            ("7 pain", 7),
            ("seven out of ten", 7),
        ):
            with self.subTest(phrase=phrase):
                parsed = parse_rating_reply(phrase)
                self.assertEqual(parsed.kind, "value")
                self.assertEqual(parsed.value, expected)

    def test_skip(self):
        self.assertEqual(parse_rating_reply("skip").kind, "skip")
        self.assertEqual(parse_rating_reply("rather not say").kind, "skip")
        self.assertEqual(parse_rating_reply("skip it").kind, "skip")
        self.assertEqual(parse_rating_reply("I'd rather skip").kind, "skip")

    def test_correction(self):
        for text in ("actually 6", "actually, I meant 6", "I meant 5", "change it to 4"):
            with self.subTest(text=text):
                result = parse_rating_reply(text)
                self.assertEqual(result.kind, "correction")
                self.assertIsNotNone(result.value)

    def test_multiple_numbers_are_ambiguous(self):
        result = parse_rating_reply("7 or 9")
        self.assertEqual(result.kind, "ambiguous")
        self.assertEqual(result.candidates, (7, 9))
        self.assertEqual(parse_rating_reply("7/10 or 9/10").kind, "ambiguous")

    def test_incidental_numbers_are_not_ratings(self):
        self.assertEqual(parse_rating_reply("I took 2 pills").kind, "none")
        self.assertEqual(parse_rating_reply("meet at 3 pm").kind, "none")
        self.assertEqual(parse_rating_reply("5 minutes").kind, "none")
        self.assertEqual(parse_rating_reply("3 tablets").kind, "none")
        self.assertIsNone(parse_rating("I took 2 pills"))

    def test_compatibility_parser(self):
        self.assertEqual(parse_rating("6"), 6)
        self.assertIsNone(parse_rating("skip"))


class SecretRedactionTests(unittest.TestCase):
    def test_redacts_12_to_19_digit_sequences(self):
        for raw in ("123456789012", "1234 5678 9012", "1234-5678-9012", "1234 5678 9012 3456"):
            with self.subTest(raw=raw):
                safe, found = redact_secrets("ID " + raw)
                self.assertTrue(found)
                self.assertNotIn(raw, safe)
                self.assertIn("[REDACTED]", safe)

    def test_does_not_redact_ten_digit_phone_numbers_by_digit_count_alone(self):
        for raw in ("1234567890", "9876543210"):
            with self.subTest(raw=raw):
                self.assertEqual(redact_secrets("call " + raw), ("call " + raw, False))

    def test_redacts_named_secrets(self):
        safe, found = redact_secrets("password=long-secret-value")
        self.assertTrue(found)
        self.assertNotIn("long-secret-value", safe)

    def test_sensitive_memory_is_blocked(self):
        allowed, reason = memory_gate("My medication is 10mg", [], enabled=True, explicit=True)
        self.assertFalse(allowed)
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
