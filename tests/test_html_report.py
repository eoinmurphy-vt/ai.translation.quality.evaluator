import contextlib
import io
import json
import os
import re
import tempfile
import unittest

from translation_quality.cli import main
from translation_quality.html_report import (_form_check, _words, build_report, findings_warnings, markdown,
                                             parse_findings)
from translation_quality.readers import compare_exports, load_layout, read_forms, read_pairs_table
from translation_quality.stats import summarise
from translation_quality.text import measure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
LEVELS = ["Critical", "Major", "Minor"]
quiet = lambda *a, **k: None


def sample_notes():
    with open(os.path.join(SAMPLES, "findings_example.md"), encoding="utf-8") as fh:
        return fh.read()


class FormsReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forms, cls.rows = read_forms([os.path.join(SAMPLES, "forms")], load_layout(), log=quiet)
        cls.page = build_report(cls.rows, "forms", ["samples/forms"], forms=cls.forms, severity_levels=LEVELS)

    def test_page_has_every_section_and_language(self):
        for text in ("<!doctype html>", 'id="ter"', 'id="scorecard"', 'id="profile"', 'id="detail"', 'id="check"',
                     'id="method"', "German (Germany)", "Japanese", "Example Language Services"):
            self.assertIn(text, self.page)

    def test_every_logged_item_is_shown(self):
        self.assertEqual(self.page.count('<article class="item">'), len(self.rows))

    def test_changes_are_highlighted(self):
        self.assertIn("<del>", self.page)
        self.assertIn("<ins>", self.page)

    def test_without_findings(self):
        self.assertNotIn('id="findings"', self.page)
        self.assertNotIn("AI can make mistakes", self.page)
        self.assertIn("Edit level (logged segments)", self.page)
        self.assertNotIn("<th>Assessment</th>", self.page)

    def test_caveats_are_worked_out_from_the_data(self):
        self.assertIn("Reading these numbers", self.page)
        self.assertIn("only the segments reviewers logged", self.page)
        self.assertIn("Japanese is measured per character", self.page)

    def test_form_check(self):
        check = self.page.split('id="check"')[1].split('id="method"')[0]
        self.assertIn("Complete forms: 2 of 2", check)
        self.assertIn("1 item with no text to compare", check)    # the German general issue
        self.assertIn("SAMPLE - invented content for testing", check)

    def test_page_is_self_contained(self):
        self.assertNotIn("<link", self.page)
        self.assertIsNone(re.search(r'\bsrc=', self.page))
        self.assertNotIn("http", self.page.split("</head>")[0])

    def test_same_language_order_in_every_table(self):
        order = re.findall(r'<div class="sname">|<span class="sname">([^<]+)</span>', self.page)
        order = [o for o in order if o]
        cats = re.findall(r'<tr><th scope="row">([^<]+)</th><td class="h', self.page)
        self.assertEqual(order, cats)


class FindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forms, cls.rows = read_forms([os.path.join(SAMPLES, "forms")], load_layout(), log=quiet)
        cls.page = build_report(cls.rows, "forms", ["x"], title="Drop 9 review", notes=sample_notes(),
                                forms=cls.forms, severity_levels=LEVELS)

    def test_title_bottom_line_and_findings(self):
        self.assertIn("<title>Drop 9 review</title>", self.page)
        header = self.page.split('id="findings"')[0]
        self.assertIn('class="bottom"', header)
        self.assertIn("German output is usable after light edits", header)
        findings = self.page.split('id="findings"')[1].split('id="ter"')[0]
        self.assertNotIn("Bottom line", findings)        # shown at the top, not repeated
        self.assertIn("<strong>German (Germany)</strong>", findings)
        self.assertIn("<ol>", findings)

    def test_ai_note(self):
        self.assertIn("AI can make mistakes", self.page.split('id="ter"')[0])
        self.assertIn("Findings</b> were drafted with AI", self.page)
        page = build_report(self.rows, "forms", ["x"], notes=sample_notes(), forms=self.forms,
                            severity_levels=LEVELS, ai_note=False)
        self.assertNotIn("AI can make mistakes", page)

    def test_assessments_fill_the_scorecard_and_language_sections(self):
        card = self.page.split('id="scorecard"')[1].split('id="profile"')[0]
        self.assertIn("<th>Assessment</th>", card)
        self.assertIn("Not usable as-is", card)
        self.assertIn("Usable with light edits", card)
        self.assertNotIn("Edit level", card)
        japanese = self.page.split('id="lang-japanese"')[1]
        self.assertIn('class="status critical"', japanese.split("</div>")[0])
        self.assertIn("One amount was misread as a count", japanese)

    def test_theme_headings_get_a_severity_tag(self):
        self.assertIn('<span class="sev tag s0"><i></i>Critical</span>', self.page)
        self.assertIn('<span class="sev tag s1"><i></i>Major</span>', self.page)

    def test_parse_findings(self):
        notes = ("# Bottom line\n\nAll good.\n\n# Language assessments\n\n"
                 "- **Japanese (JP)**: Good (evidence: strong, 9 items). Fine.\n"
                 "- **German**: Needs targeted fixes (evidence: limited, 1 item). Wraps\n  onto a second line.\n"
                 "- **Klingon**: Good (evidence: none, 0 items). Not in the data.\n")
        bottom, body, assessments, unmatched = parse_findings(notes, ["Japanese", "German (Germany)"])
        self.assertEqual(bottom, "All good.")
        self.assertNotIn("Bottom line", body)
        self.assertEqual(assessments["Japanese"]["status"], "Good")
        self.assertEqual(assessments["German (Germany)"]["cls"], "warning")
        self.assertEqual(assessments["German (Germany)"]["reason"], "Wraps onto a second line.")
        self.assertEqual(unmatched, ["Klingon"])

    def test_findings_warnings(self):
        warnings = findings_warnings("# Summary\n\nText.", self.rows)
        self.assertTrue(any("Bottom line" in w for w in warnings))
        self.assertTrue(any("No language assessment" in w for w in warnings))
        self.assertEqual(findings_warnings(sample_notes(), self.rows), [])


class FormCheckTests(unittest.TestCase):
    def test_flags_gaps_and_locale_in_team_field(self):
        rows = [{"language": "Thai", "file": "t.xlsm", "severity": "", "category": "C", "comment": "",
                 "task": "Task", "raw": "a", "raw_measured": "a", "metrics": None, "unit": "char"},
                {"language": "Thai", "file": "t.xlsm", "severity": "Minor", "category": "C", "comment": "ok",
                 "task": "Task", "raw": "a\nb", "raw_measured": "a", "metrics": None, "unit": "char"}]
        forms = [{"file": "t.xlsm", "language": "Thai", "language_entered": "Thai", "team": "th_TH",
                  "project": "P", "word_count": "", "overall_comment": "Fine"}]
        html_out = _form_check(summarise(rows), forms, rows, LEVELS)
        for text in ("Complete forms: 0 of 1", "Missing: word count", "1 without severity", "1 without comment",
                     "Team field holds a locale code", "1 Minor item logged", "1 cell with more than one AI output",
                     "2 items with no text to compare"):
            self.assertIn(text, html_out)

    def test_word_counts_are_formatted(self):
        self.assertEqual(_words("1204"), "1,204")
        self.assertEqual(_words(1325), "1,325")
        self.assertEqual(_words("~700"), "~700")
        self.assertEqual(_words("1,134 words (99 segments)"), "1,134 words (99 segments)")


class PairsReportTests(unittest.TestCase):
    def test_unchanged_segments_are_counted_not_listed(self):
        rows = compare_exports(os.path.join(SAMPLES, "exports", "de_raw.json"),
                               os.path.join(SAMPLES, "exports", "de_final.json"), "de-DE")
        page = build_report(rows, "pairs", ["x"])
        edited = sum(1 for r in rows if r["metrics"] and r["metrics"]["edits"])
        self.assertEqual(page.count('<article class="item">'), edited)
        self.assertIn("1 unchanged segment(s) are not shown", page)
        self.assertIn('id="effort"', page)
        self.assertNotIn('id="check"', page)
        self.assertIn("fewer than 20 segments", page)

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
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(args))
        return code, out.getvalue()

    def test_notes_option_writes_report_next_to_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "result.xlsx")
            code, stdout = self.run_cli("forms", os.path.join(SAMPLES, "forms"), "-o", out,
                                        "--notes", os.path.join(SAMPLES, "findings_example.md"))
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "result.html")))
            self.assertNotIn("Findings check", stdout)

    def test_findings_problems_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = os.path.join(tmp, "notes.md")
            with open(notes, "w", encoding="utf-8") as fh:
                fh.write("# Summary\n\nNo assessments here.\n")
            code, stdout = self.run_cli("forms", os.path.join(SAMPLES, "forms"), "-o", os.path.join(tmp, "r.xlsx"),
                                        "--notes", notes)
        self.assertEqual(code, 0)
        self.assertIn("Findings check: No language assessment for", stdout)

    def test_no_ai_note_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "r.xlsx")
            self.run_cli("forms", os.path.join(SAMPLES, "forms"), "-o", out, "--no-ai-note",
                         "--notes", os.path.join(SAMPLES, "findings_example.md"))
            with open(os.path.join(tmp, "r.html"), encoding="utf-8") as fh:
                self.assertNotIn("AI can make mistakes", fh.read())

    def test_html_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "report.html")
            code, _ = self.run_cli("table", os.path.join(SAMPLES, "pairs.csv"), "-o", os.path.join(tmp, "t.xlsx"),
                                   "--html-output", target)
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(target))

    def test_missing_notes_file_explains_what_to_do(self):
        missing = os.path.join(SAMPLES, "no_such_findings.md")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = main(["table", os.path.join(SAMPLES, "pairs.csv"), "--notes", missing])
        message = err.getvalue()
        self.assertEqual(code, 2)
        for text in ("there's no findings file at", "doesn't write them", "leave out --notes", "/write-findings",
                     "findings_example.md"):      # the findings files that do exist in that folder are listed
            self.assertIn(text, message)

    def test_missing_notes_folder_lists_the_data_folder_instead(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = main(["table", os.path.join(SAMPLES, "pairs.csv"), "--notes", "no/such/folder/notes.md"])
        self.assertEqual(code, 2)
        self.assertIn("data", err.getvalue().splitlines()[-1])


class LanguageOverrideTests(unittest.TestCase):
    def test_override_changes_the_language_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "layout.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"language_overrides": {"de-DE": "de"}}, fh)
            _forms, rows = read_forms([os.path.join(SAMPLES, "forms")], load_layout(path), log=quiet)
        self.assertIn("German", {r["language"] for r in rows})
        self.assertNotIn("German (Germany)", {r["language"] for r in rows})


if __name__ == "__main__":
    unittest.main()
