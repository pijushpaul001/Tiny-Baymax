import unittest

from baymax.detection import detect, parse_rating, parse_rating_reply
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


class FigurativeDifficultyTests(unittest.TestCase):
    def test_common_figurative_pain_phrases_do_not_prompt_a_rating(self):
        self.assertEqual(detect("this project is a headache").type, "none")
        self.assertEqual(detect("I am burning dinner").type, "none")

    def test_apostrophe_variants_keep_urgent_phrases_detectable(self):
        for text in ("I cant breathe", "I can't breathe", "I can’t breathe",
                     "it wont stop bleeding", "it won't stop bleeding", "it won’t stop bleeding"):
            with self.subTest(text=text):
                self.assertEqual(detect(text).red_flag, "urgent_medical")

    def test_common_self_harm_phrases_are_detected_without_matching_leave(self):
        for text in ("I don’t want to live", "I dont want to live", "I don't want to be here",
                     "I do not want to be alive", "there is no reason to live",
                     "I would be better off dead", "I want to end it all", "take my own life"):
            with self.subTest(text=text):
                self.assertEqual(detect(text).red_flag, "self_harm")
        self.assertEqual(detect("I don't want to leave the house").red_flag, "")

    def test_literal_pain_and_chest_tightness_are_still_detected(self):
        self.assertEqual(detect("my head hurts").type, "physical")
        self.assertEqual(detect("my leg is burning").type, "physical")
        result = detect("my chest feels tight")
        self.assertEqual(result.red_flag, "urgent_medical")


class SecretRedactionTests(unittest.TestCase):
    def test_redacts_12_to_19_digit_sequences(self):
        for raw in ("123456789012", "1234 5678 9012", "1234-5678-9012", "1234 5678 9012 3456"):
            with self.subTest(raw=raw):
                safe, found = redact_secrets("ID " + raw)
                self.assertTrue(found)
                self.assertNotIn(raw, safe)
                self.assertIn("[REDACTED]", safe)

    def test_redacts_all_of_long_digit_groups_and_avoids_short_group_false_positive(self):
        raw = "1234 5678 9012 3456 7890 1234"
        safe, found = redact_secrets("ID " + raw)
        self.assertTrue(found)
        self.assertNotIn("7890 1234", safe)
        self.assertIn("[REDACTED]", safe)
        self.assertEqual(redact_secrets("numbers 10 20 30 40 50 60"), ("numbers 10 20 30 40 50 60", False))

    def test_secret_keyword_in_ordinary_sentence_is_not_redacted(self):
        self.assertEqual(redact_secrets("the token was rejected"), ("the token was rejected", False))

    def test_redacts_multi_word_assigned_passphrases(self):
        cases = (
            ("password is correct horse battery staple", ("correct", "horse", "battery", "staple")),
            ("passcode: blue river quiet mountain", ("blue", "river", "quiet", "mountain")),
            ("api_key=alpha beta gamma", ("alpha", "beta", "gamma")),
        )
        for raw, secret_words in cases:
            with self.subTest(raw=raw):
                safe, found = redact_secrets(raw)
                self.assertTrue(found)
                self.assertIn("[REDACTED]", safe)
                for word in secret_words:
                    self.assertNotIn(word, safe)

    def test_multiword_secret_redaction_preserves_following_symptom_sentence(self):
        cases = (
            ("my password is hunter2. My head hurts really bad", "My head hurts really bad"),
            ("my pin is 4821. I feel sad today", "I feel sad today"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                safe, found = redact_secrets(raw)
                self.assertTrue(found)
                self.assertIn("[REDACTED]", safe)
                self.assertIn(expected, safe)

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
