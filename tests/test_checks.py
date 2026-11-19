"""Placeholder, URL, link and tag checks, and client placeholder rules. All text is invented."""
import contextlib
import io
import json
import os
import tempfile
import unittest

import openpyxl

from translation_quality.checks import check_row, load_rules, placeholders, run_checks, summarise_checks
from translation_quality.cli import main
from translation_quality.readers import InputError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_RULES = os.path.join(ROOT, "config", "placeholder_rules.example.json")
NO_RULES = load_rules(None)
RULES = load_rules(EXAMPLE_RULES)


def check(source, raw, final="", code="de-DE", rules=NO_RULES):
    issues, _found = check_row({"source": source, "raw": raw, "final": final, "code": code}, rules)
    return issues


def summary(issues):
    return [(i["text"], i["level"], i["check"], i["status"]) for i in issues]


class PlaceholderTests(unittest.TestCase):
    def test_notations_count_as_the_same_placeholder(self):
        self.assertEqual(check("Unlock your 1:planName plan", "Desbloquea tu plan [%1$s:planName].",
                               "Activa tu plan {{planName}}.", code="es-US"), [])
        self.assertEqual(check("Pay %s now", "Zahle [%s] jetzt"), [])

    def test_number_stuck_to_the_editor_notation(self):
        self.assertEqual(check("Send 200 {{currencyCode}}", "200 {{currencyCode}} senden",
                               "2001:currencyCode senden"), [])

    def test_trailing_full_stop_is_not_part_of_the_name(self):
        names = [p[2][1] for p in placeholders("sending from 1:sentenceNameSendCountry.")]
        self.assertEqual(names, ["sentenceNameSendCountry"])

    def test_missing_placeholder_fixed_in_review(self):
        issues = check("Pay {{amount}} today", "Heute bezahlen", "Heute {{amount}} bezahlen")
        self.assertEqual(summary(issues), [("raw", "Error", "Placeholders", "Fixed in review")])
        self.assertIn("{{amount}} is missing", issues[0]["message"])

    def test_error_left_in_final(self):
        issues = check("Pay {{amount}} today", "Heute bezahlen", "Heute zahlen")
        self.assertEqual(summary(issues), [("raw", "Error", "Placeholders", "Left in final")])

    def test_error_introduced_in_review(self):
        issues = check("Pay {{amount}} today", "Heute {{amount}} bezahlen", "Heute bezahlen")
        self.assertEqual(summary(issues), [("final", "Error", "Placeholders", "Introduced in review")])

    def test_count_and_rename(self):
        issues = check("{{a}} or {{a}}", "{{a}}")
        self.assertIn("appears once, but twice in the source", issues[0]["message"])
        issues = check("Hello {{name}}", "Hallo {{nombre}}")
        self.assertEqual(len(issues), 1)
        self.assertIn("{{name}} was changed to {{nombre}}", issues[0]["message"])

    def test_broken_braces_and_translated_names(self):
        checks = [i["check"] for i in check("Hello {{name}}", "Hallo {{name}")]
        self.assertIn("Broken placeholder", checks)
        checks = [i["check"] for i in check("{{corridor.sendingCountry.name}}", "{{corridor.paísEmisor.nombre}}",
                                            code="es")]
        self.assertIn("Broken placeholder", checks)

    def test_icu_plurals_are_not_broken_placeholders(self):
        text = "{count, plural, one {# item} other {# items}} and {n, plural, one {#} other {#}}"
        self.assertEqual(check(text, text), [])

    def test_no_final_text(self):
        issues = check("Pay {{amount}}", "Bezahlen", "")
        self.assertEqual(summary(issues), [("raw", "Error", "Placeholders", "No final text")])


class LinkAndTagTests(unittest.TestCase):
    def test_translated_url_path_after_placeholder(self):
        issues = check("{{remitlyDynamicBaseURL}}/oauth/login", "{{remitlyDynamicBaseURL}}/oauth/로그인",
                       "{{remitlyDynamicBaseURL}}/oauth/login", code="ko-KR")
        self.assertEqual(summary(issues), [("raw", "Error", "URL path", "Fixed in review")])

    def test_markdown_link_with_url_placeholder(self):
        source = "Read [how much it costs]({{baseUrl}}/help/article/costs)."
        issues = check(source, "Lies [die Kosten]({{baseUrl}}/hilfe/artikel/kosten).")
        self.assertEqual([i["check"] for i in issues], ["URL path"])
        self.assertEqual(check(source, "Lies [die Kosten]({{baseUrl}}/help/article/costs)."), [])

    def test_changed_literal_link_is_a_check(self):
        issues = check("Visit [our site](https://www.example.com/)", "Besuche [unsere Seite](https://www.example.de/)")
        self.assertEqual(summary(issues), [("raw", "Check", "Link", "No final text")])

    def test_missing_tag_is_a_check(self):
        issues = check("Hello<br>World", "Hallo Welt", "Hallo<br/>Welt")
        self.assertEqual(summary(issues), [("raw", "Check", "Tags", "Fixed in review")])


class RuleTests(unittest.TestCase):
    def test_example_rules_load(self):
        self.assertEqual([r["id"] for r in RULES["rules"]], ["includes-preposition", "includes-article"])

    def test_preposition_before_phrase_placeholder(self):
        issues = check("Send money {{trip.destination.toPhrase}}", "Geld nach {{trip.destination.toPhrase}} senden",
                       "Geld {{trip.destination.toPhrase}} senden", rules=RULES)
        self.assertEqual(summary(issues), [("raw", "Error", "Word before placeholder", "Fixed in review")])
        self.assertIn("“nach” before {{trip.destination.toPhrase}}", issues[0]["message"])

    def test_elided_article_and_punctuation(self):
        issues = check("Money {{trip.origin.fromPhrase}}", "Argent d'{{trip.origin.fromPhrase}}", code="fr-FR",
                       rules=RULES)
        self.assertEqual([i["check"] for i in issues], ["Word before placeholder"])
        self.assertEqual(check("Money {{trip.origin.fromPhrase}}", "Geld: {{trip.origin.fromPhrase}}", rules=RULES), [])

    def test_turkish_suffix_after_phrase_placeholder(self):
        issues = check("Send {{trip.destination.toPhrase}}", "{{trip.destination.toPhrase}}'a gönder", code="tr-TR",
                       rules=RULES)
        self.assertEqual([i["check"] for i in issues], ["Suffix after placeholder"])

    def test_source_issue(self):
        issues = check("Send money to {{trip.destination.toPhrase}}", "Geld {{trip.destination.toPhrase}} senden",
                       rules=RULES)
        self.assertEqual(summary(issues), [("source", "Source issue", "Word before placeholder", "Report to client")])

    def test_allowed_swap_is_a_note(self):
        issues = check("Send money from {{trip.origin.name}}", "Geld {{trip.origin.fromPhrase}} senden", rules=RULES)
        self.assertEqual(summary(issues), [("raw", "Note", "Placeholders", "Allowed")])

    def test_language_without_a_list_is_not_checked(self):
        self.assertEqual(check("Send {{trip.destination.toPhrase}}", "送金 {{trip.destination.toPhrase}}", code="ja",
                               rules=RULES), [])

    def test_bad_rules_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rules, expected in (({"rules": [{"placeholders": "("}]}, "valid regular expression"),
                                    ({"rules": [{"placeholders": "x", "level": "Fatal"}]}, "Error"),
                                    ({"rules": [{"id": "r"}]}, "placeholders")):
                path = os.path.join(tmp, "rules.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(rules, fh)
                with self.assertRaises(InputError) as ctx:
                    load_rules(path)
                self.assertIn(expected, str(ctx.exception))


class SummaryTests(unittest.TestCase):
    def test_counts_each_item_once(self):
        rows = [
            {"language": "German", "code": "de", "source": "{{a}} {{b}}", "raw": "x", "final": "{{a}} {{b}}"},
            {"language": "German", "code": "de", "source": "{{a}}", "raw": "y", "final": "z"},
            {"language": "German", "code": "de", "source": "plain", "raw": "schlicht", "final": "schlicht"},
        ]
        run_checks(rows, NO_RULES)
        s = summarise_checks(rows)["languages"]["German"]
        self.assertEqual((s["items"], s["with_placeholders"], s["ai_errors"], s["fixed"], s["left_in_final"]),
                         (3, 2, 2, 1, 1))

    def test_without_source_compares_raw_and_final(self):
        issues = check("", "{{a}} Text", "Text")
        self.assertEqual(summary(issues), [("final", "Check", "Placeholders", "Changed in review")])


class OutputTests(unittest.TestCase):
    def test_forms_run_writes_checks_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "r.xlsx")
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                code = main(["forms", os.path.join(ROOT, "samples", "forms"), "-o", out, "--html",
                             "--json", os.path.join(tmp, "r.json"), "--rules", EXAMPLE_RULES])
            self.assertEqual(code, 0)
            self.assertIn("Placeholder checks (client rules from", printed.getvalue())
            with open(os.path.join(tmp, "r.json"), encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIn("placeholder_checks", data)
            self.assertTrue(all("checks" in r for r in data["rows"]))
            wb = openpyxl.load_workbook(out)
            self.assertIn("Placeholder checks", wb.sheetnames)
            wb.close()
            with open(os.path.join(tmp, "r.html"), encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn('id="placeholders"', page)
            self.assertIn("placeholder_rules.example.json", page)

    def test_missing_rules_file_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main(["forms", os.path.join(ROOT, "samples", "forms"), "-o", os.path.join(tmp, "r.xlsx"),
                             "--rules", os.path.join(tmp, "nope.json")])
            self.assertEqual(code, 2)
            self.assertIn("placeholder rules file", err.getvalue())


if __name__ == "__main__":
    unittest.main()
