import unittest

from cad_text import decode_architect_text


class LegacyHebrewTests(unittest.TestCase):
    def encode_visual(self, text):
        return text.encode("cp862").decode("cp1252", errors="surrogateescape")

    def test_void_and_balcony_labels(self):
        for logical in ("\u05d7\u05dc\u05dc \u05db\u05e4\u05d5\u05dc", "\u05de\u05e8\u05e4\u05e1\u05ea", "\u05de\u05d8\u05d1\u05d7\u05d5\u05df"):
            self.assertEqual(decode_architect_text(self.encode_visual(logical[::-1])), logical)

    def test_decimal_measurement_is_not_reversed(self):
        visual = "\u05e8''\u05de 16.2"
        self.assertEqual(decode_architect_text(self.encode_visual(visual)), "16.2 \u05de''\u05e8")

    def test_other_text_remains_intact(self):
        for text in ("H=+2.20", "285", "\u05de\u05e8\u05e4\u05e1\u05ea", "kitchen"):
            self.assertEqual(decode_architect_text(text), text)


if __name__ == "__main__":
    unittest.main()
