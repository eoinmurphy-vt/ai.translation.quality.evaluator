import unittest

from translation_quality.ter import ter
from translation_quality.text import diff_ops, measure, tokenize, unit_for

PH = "ph:code"


class TerTests(unittest.TestCase):
    def test_published_reference_example(self):
        # Snover et al. (2006): 1 shift + 2 substitutions + 1 insertion over 13 reference words.
        hyp = "this week the saudis denied information published in the new york times".split()
        ref = "saudi arabia denied this week information published in the american new york times".split()
        t = ter(hyp, ref)
        self.assertEqual((t["edits"], t["ref_len"], t["moves"]), (4, 13, 1))

    def test_identical_text_has_no_edits(self):
        self.assertEqual(ter(list("abcd"), list("abcd"))["edits"], 0)

    def test_moved_phrase_counts_as_one_edit(self):
        t = ter("c d a b".split(), "a b c d".split())
        self.assertEqual((t["edits"], t["moves"]), (1, 1))

    def test_everything_added(self):
        t = ter([], ["a", "b"])
        self.assertEqual((t["added"], t["edits"]), (2, 2))

    def test_edit_breakdown_adds_up(self):
        t = ter("the cat sat on mat".split(), "a cat sat on the red mat".split())
        self.assertEqual(t["edits"], t["added"] + t["removed"] + t["replaced"] + t["moves"])


class TokenTests(unittest.TestCase):
    def test_placeholder_notations_are_the_same_token(self):
        self.assertEqual(tokenize("Send 5,000 {{code}} now", "word"), tokenize("Send 5,000 1:code now", "word"))

    def test_number_glued_to_lokalise_placeholder(self):
        self.assertEqual(tokenize("5,0001:code", "word"), ["5,000", PH])

    def test_other_placeholders_and_tags_are_single_tokens(self):
        tokens = tokenize("<b>Hi</b> %s and %1$s and {0} and [%s]", "word")
        for tok in ("<b>", "</b>", "%s", "%1$s", "{0}", "[%s]"):
            self.assertIn(f"{tok.lower()}", tokens)

    def test_percent_sign_in_text_is_not_a_placeholder(self):
        self.assertNotIn("% d", tokenize("50 % de descuento", "word"))

    def test_japanese_is_split_into_characters(self):
        self.assertEqual(tokenize("荷物を追跡", "char"), list("荷物を追跡"))

    def test_thai_marks_stay_with_their_consonant(self):
        self.assertEqual(tokenize("ส่ง", "char"), ["ส่", "ง"])

    def test_numbers_stay_whole(self):
        self.assertEqual(tokenize("10.000 USD", "word"), ["10.000", "usd"])


class MeasureTests(unittest.TestCase):
    def test_case_differences_are_not_edits(self):
        self.assertEqual(measure("Hello world", "hello world", "word")["edits"], 0)

    def test_empty_side_is_not_measured(self):
        self.assertIsNone(measure("", "text", "word"))
        self.assertIsNone(measure("text", "  ", "word"))

    def test_rates(self):
        m = measure("Retours gratuits dans les 30 jours", "Retours gratuits sous 30 jours", "word")
        self.assertAlmostEqual(m["ter"], m["edits"] / 5)
        self.assertGreater(m["char_rate"], 0)

    def test_ter_can_exceed_100_percent_when_final_is_shorter(self):
        self.assertGreater(measure("あなたのパッケージを追跡する", "荷物を追跡", "char")["ter"], 1)


class UnitTests(unittest.TestCase):
    def test_units_by_language(self):
        self.assertEqual(unit_for("ja"), "char")
        self.assertEqual(unit_for("zh-CN"), "char")
        self.assertEqual(unit_for("th_TH"), "char")
        self.assertEqual(unit_for("jp"), "char")      # country code used for Japanese
        self.assertEqual(unit_for("de-DE"), "word")
        self.assertEqual(unit_for("ko-KR"), "word")   # Korean separates words with spaces

    def test_unknown_language_is_decided_by_script(self):
        self.assertEqual(unit_for("", ["ส่งความสุข"]), "char")
        self.assertEqual(unit_for(None, ["plain text"]), "word")


class DiffTests(unittest.TestCase):
    def rebuild(self, ops, keep):
        return "".join(text for op, text in ops if op in keep)

    def test_ops_rebuild_both_texts(self):
        raw, final = "Ihre Bestellung wird verschickt.", "Ihre Bestellung wird versendet."
        ops = diff_ops(raw, final, "word")
        self.assertEqual(self.rebuild(ops, ("equal", "insert")), final)
        self.assertEqual(self.rebuild(ops, ("equal", "delete")), raw)

    def test_small_unchanged_islands_are_folded(self):
        ops = diff_ops("Wir haben Ihre Bestellung heute erhalten", "Deine Bestellung ist heute bei uns eingegangen",
                       "word")
        self.assertLessEqual(sum(1 for op, _ in ops if op == "delete"), 1)

    def test_unchanged_text_is_one_equal_run(self):
        self.assertEqual(diff_ops("Kasse", "Kasse", "word"), [("equal", "Kasse")])


if __name__ == "__main__":
    unittest.main()
