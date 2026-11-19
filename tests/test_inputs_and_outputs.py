"""End-to-end tests on the invented files in samples/."""
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import openpyxl
from openpyxl.cell.rich_text import CellRichText

from translation_quality.cli import main
from translation_quality.excel import _fold_whitespace_runs, write_forms_workbook, write_pairs_workbook
from translation_quality.readers import (InputError, compare_exports, load_layout, read_forms,
                                         read_pairs_table)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
FORMS = os.path.join(SAMPLES, "forms")
EXPORTS = os.path.join(SAMPLES, "exports")
quiet = lambda *a, **k: None


class FormTests(unittest.TestCase):
    def setUp(self):
        self.forms, self.rows = read_forms([FORMS], load_layout(), log=quiet)

    def test_reads_every_form_and_item(self):
        self.assertEqual(len(self.forms), 2)
        self.assertEqual(len(self.rows), 7)
        german = next(f for f in self.forms if f["code"] == "de-DE")
        self.assertEqual(german["team"], "Example Language Services")
        self.assertEqual(german["language_entered"], "German (Germany)")

    def test_general_issue_is_listed_but_not_measured(self):
        general = [r for r in self.rows if r["source"] == "General issue"]
        self.assertEqual(len(general), 1)
        self.assertIsNone(general[0]["metrics"])

    def test_units_and_categories(self):
        ja = [r for r in self.rows if r["code"] == "ja-JP"]
        self.assertTrue(all(r["unit"] == "char" for r in ja))
        self.assertEqual({r["category"] for r in self.rows}, {"Fluency & Style", "Compliance", "Accuracy"})

    def test_layout_with_wrong_sheet_name_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "layout.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"sheet": "Not there"}, fh)
            with self.assertRaises(InputError):
                read_forms([FORMS], load_layout(path), log=quiet)


class ExportTests(unittest.TestCase):
    def test_nested_json_exports(self):
        rows = compare_exports(os.path.join(EXPORTS, "de_raw.json"), os.path.join(EXPORTS, "de_final.json"),
                               "de-DE", os.path.join(EXPORTS, "en_source.json"))
        self.assertEqual(len(rows), 6)
        title = next(r for r in rows if r["key"] == "checkout::title")
        self.assertEqual(title["metrics"]["edits"], 0)
        self.assertEqual(title["source"], "Checkout")

    def test_xliff_exports_bring_their_source_text(self):
        rows = compare_exports(os.path.join(EXPORTS, "ja_raw.xliff"), os.path.join(EXPORTS, "ja_final.xliff"), "ja")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["source"] for r in rows))
        self.assertEqual(rows[0]["unit"], "char")

    def test_keys_missing_on_one_side_are_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, final = os.path.join(tmp, "raw.json"), os.path.join(tmp, "final.json")
            for path, data in ((raw, {"a": "Hallo Welt", "only_raw": "x"}),
                               (final, {"a": "Hallo, Welt", "only_final": "y"})):
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
            rows = {r["key"]: r for r in compare_exports(raw, final, "de")}
        self.assertIsNotNone(rows["a"]["metrics"])
        self.assertIn("Missing from the raw AI export", rows["only_final"]["notes"])
        self.assertIn("Missing from the final export", rows["only_raw"]["notes"])

    def test_csv_export_with_named_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in (("raw.csv", "Melden Sie sich an"), ("final.csv", "Melde dich an")):
                with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as fh:
                    csv.writer(fh).writerows([["key", "en", "de"], ["signin", "Sign in", text]])
            rows = compare_exports(os.path.join(tmp, "raw.csv"), os.path.join(tmp, "final.csv"), "de",
                                   text_column="de")
        self.assertEqual(rows[0]["final"], "Melde dich an")

    def test_pairs_table_with_alternative_column_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pairs.csv")
            with open(path, "w", encoding="utf-8", newline="") as fh:
                csv.writer(fh).writerows([["Key ID", "Locale", "Raw AI", "Corrected"],
                                          ["k1", "fr-FR", "Retours gratuits dans les 30 jours",
                                           "Retours gratuits sous 30 jours"]])
            rows = read_pairs_table(path)
        self.assertEqual(rows[0]["language"], "French (France)")
        self.assertGreater(rows[0]["metrics"]["edits"], 0)

    def test_pairs_table_needs_core_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            with open(path, "w", encoding="utf-8", newline="") as fh:
                csv.writer(fh).writerows([["key", "text"], ["a", "b"]])
            with self.assertRaises(InputError):
                read_pairs_table(path)


class WorkbookTests(unittest.TestCase):
    def test_forms_workbook(self):
        forms, rows = read_forms([FORMS], load_layout(), log=quiet)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "forms.xlsx")
            write_forms_workbook(forms, rows, out, ["Critical", "Major", "Minor"], [FORMS])
            wb = openpyxl.load_workbook(out, rich_text=True)
            self.assertEqual(wb.sheetnames, ["About", "Summary", "Segments", "Forms"])
            summary = wb["Summary"]
            self.assertEqual(summary["A1"].value, "Language")
            self.assertEqual([summary.cell(row=r, column=1).value for r in (2, 3, 4)],
                             ["German (Germany)", "Japanese", "All languages"])
            self.assertTrue(str(summary["L2"].value).startswith("=IF("))
            segments = wb["Segments"]
            header = [c.value for c in segments[1]]
            changes = segments.cell(row=2, column=header.index("Changes (raw to corrected)") + 1).value
            self.assertIsInstance(changes, CellRichText)
            wb.close()

    def test_pairs_workbook_has_one_row_per_language_plus_total(self):
        rows = read_pairs_table(os.path.join(SAMPLES, "pairs.csv"))
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "pairs.xlsx")
            write_pairs_workbook(rows, out, ["pairs.csv"])
            wb = openpyxl.load_workbook(out)
            names = [wb["Summary"].cell(row=r, column=1).value for r in range(2, 6)]
            wb.close()
        self.assertEqual(names, ["German (Germany)", "Japanese", "French (France)", "All languages"])

    def test_whitespace_only_runs_are_folded(self):
        # A lone ' ' run makes Excel refuse to open the workbook.
        ops = _fold_whitespace_runs([("equal", "a"), ("insert", "b"), ("equal", " "), ("delete", "c")])
        self.assertTrue(all(text.strip() for _, text in ops))
        self.assertEqual("".join(t for _, t in ops), "ab c")


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_every_mode_writes_a_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = {
                "forms": ["forms", FORMS],
                "compare": ["compare", "--raw", os.path.join(EXPORTS, "de_raw.json"),
                            "--final", os.path.join(EXPORTS, "de_final.json"), "--lang", "de-DE"],
                "table": ["table", os.path.join(SAMPLES, "pairs.csv")],
            }
            for name, args in runs.items():
                with self.subTest(mode=name):
                    out = os.path.join(tmp, f"{name}.xlsx")
                    code, stdout, _ = self.run_cli(*args, "-o", out, "--json", out + ".json")
                    self.assertEqual(code, 0)
                    self.assertTrue(os.path.isfile(out))
                    self.assertIn("Workbook written", stdout)

    def test_output_folders_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "new", "folder", "result.xlsx")
            data = os.path.join(tmp, "other", "result.json")
            code, _, _ = self.run_cli("forms", FORMS, "-o", out, "--json", data, "--html")
            self.assertEqual(code, 0)
            for path in (out, data, os.path.splitext(out)[0] + ".html"):
                self.assertTrue(os.path.isfile(path), path)
            with open(data, encoding="utf-8") as fh:
                payload = json.load(fh)
            self.assertEqual(payload["mode"], "forms")
            self.assertEqual(payload["severity_levels"], ["Critical", "Major", "Minor"])
            self.assertIn("overall_comment", payload["forms"][0])

    def test_missing_input_is_a_clear_error(self):
        code, _, err = self.run_cli("table", "no_such_file.csv", "-o", os.devnull)
        self.assertEqual(code, 2)
        self.assertIn("Error", err)

    def test_selftest_passes(self):
        self.assertEqual(self.run_cli("selftest")[0], 0)


if __name__ == "__main__":
    unittest.main()
