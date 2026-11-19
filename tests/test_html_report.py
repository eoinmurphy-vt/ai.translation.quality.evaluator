import contextlib
import io
import os
import re
import tempfile
import unittest

from translation_quality.cli import main
from translation_quality.html_report import build_report, markdown
from translation_quality.readers import compare_exports, load_layout, read_forms, read_pairs_table
from translation_quality.text import measure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
LEVELS = ["Critical", "Major", "Minor"]
quiet = lambda *a, **k: None


class FormsReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forms, cls.rows = read_forms([os.path.join(SAMPLES, "forms")], load_layout(), log=quiet)
        cls.page = build_report(cls.rows, "forms", ["samples/forms"], forms=cls.forms, severity_levels=LEVELS)

    def test_page_has_every_section_and_language(self):
        for text in ("<!doctype html>", 'id="ter"', 'id="scorecard"', 'id="profile"', 'id="detail"', 'id="method"',
                     "German (Germany)", "Japanese", "Example Language Services"):
            self.assertIn(text, self.page)

    def test_every_logged_item_is_shown(self):
        self.assertEqual(self.page.count('<article class="item">'), len(self.rows))

    def test_changes_are_highlighted(self):
        self.assertIn("<del>", self.page)
        self.assertIn("<ins>", self.page)

    def test_no_findings_section_without_notes(self):
        self.assertNotIn('id="findings"', self.page)

    def test_page_is_self_contained(self):
        self.assertNotIn("<link", self.page)
        self.assertIsNone(re.search(r'\bsrc=', self.page))
        self.assertNotIn("http", self.page.split("</head>")[0])

    def test_notes_and_title(self):
        with open(os.path.join(SAMPLES, "findings_example.md"), encoding="utf-8") as fh:
            notes = fh.read()
        page = build_report(self.rows, "forms", ["x"], title="Drop 9 review", notes=notes, forms=self.forms,
                            severity_levels=LEVELS)
        self.assertIn("<title>Drop 9 review</title>", page)
        self.assertIn('id="findings"', page)
        self.assertIn("<strong>German</strong>", page)
        self.assertIn("<ol>", page)


class PairsReportTests(unittest.TestCase):
    def test_unchanged_segments_are_counted_not_listed(self):
        rows = compare_exports(os.path.join(SAMPLES, "exports", "de_raw.json"),
                               os.path.join(SAMPLES, "exports", "de_final.json"), "de-DE")
        page = build_report(rows, "pairs", ["x"])
        edited = sum(1 for r in rows if r["metrics"] and r["metrics"]["edits"])
        self.assertEqual(page.count('<article class="item">'), edited)
        self.assertIn("1 unchanged segment(s) are not shown", page)
        self.assertIn('id="effort"', page)

    def test_content_is_escaped(self):
        rows = read_pairs_table(os.path.join(SAMPLES, "pairs.csv"))
        rows[0] = dict(rows[0], final="<script>alert(1)</script> Hallo", key='"><img onerror=x>')
        rows[0]["metrics"] = measure(rows[0]["raw"], rows[0]["final"], rows[0]["unit"])
        page = build_report(rows, "pairs", ["<b>input</b>"])
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img onerror", page)
        self.assertNotIn("<b>input</b>", page)
        self.assertIn("&lt;script&gt;", page)


class MarkdownTests(unittest.TestCase):
    def test_blocks(self):
        out = markdown("# Title\n\nSome **bold** and *italic* text.\n\n- one\n- two\n\n1. first\n2. second\n\n> quote")
        for text in ("<h3>Title</h3>", "<strong>bold</strong>", "<em>italic</em>", "<ul><li>one</li><li>two</li></ul>",
                     "<ol><li>first</li><li>second</li></ol>", "<blockquote>quote</blockquote>"):
            self.assertIn(text, out)

    def test_links_are_limited_to_web_and_mail(self):
        self.assertIn('<a href="https://example.com">site</a>', markdown("[site](https://example.com)"))
        self.assertNotIn("<a", markdown("[x](javascript:alert(1))"))

    def test_html_in_notes_is_escaped(self):
        self.assertIn("&lt;script&gt;", markdown("<script>x</script>"))


class CommandLineTests(unittest.TestCase):
    def test_notes_option_writes_report_next_to_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "result.xlsx")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["forms", os.path.join(SAMPLES, "forms"), "-o", out,
                             "--notes", os.path.join(SAMPLES, "findings_example.md")])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "result.html")))

    def test_html_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "report.html")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["table", os.path.join(SAMPLES, "pairs.csv"), "-o", os.path.join(tmp, "t.xlsx"),
                             "--html-output", target])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(target))

    def test_missing_notes_file_is_a_clear_error(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = main(["table", os.path.join(SAMPLES, "pairs.csv"), "--notes", "no_such_notes.md"])
        self.assertEqual(code, 2)
        self.assertIn("notes file", err.getvalue())


if __name__ == "__main__":
    unittest.main()
