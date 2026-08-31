import unittest

from experiments.asr_baseline.metrics import normalize_text, word_error_rate


class AsrMetricsTests(unittest.TestCase):
    def test_normalization_preserves_accents_and_removes_punctuation(self):
        self.assertEqual(normalize_text("  Olá, MUNDO!  "), "olá mundo")

    def test_word_error_rate_counts_substitution(self):
        self.assertAlmostEqual(word_error_rate("um teste simples", "um teste diferente"), 1 / 3)

    def test_word_error_rate_is_none_without_reference_words(self):
        self.assertIsNone(word_error_rate("...", "qualquer texto"))


if __name__ == "__main__":
    unittest.main()

