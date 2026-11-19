"""Creates the sample files in this folder. All content is invented for testing; no client data.

Run from the repository root:  python samples/make_samples.py
"""
import csv
import json
import os

import openpyxl
from openpyxl.styles import Font

HERE = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = {
    "accuracy": "Accuracy - Omission, addition, mistranslation, source misinterpretation, misleading translation, "
                "untranslated text or DNT localized and Tags (misplaced, missing, added)",
    "fluency": "Fluency & Style - Literal translation, lack of fluency, unidiomatic language, inappropriate style, "
               "register or tone of voice",
    "compliance": "Compliance - Glossary, internal consistency, Style Guide",
}

FORMS = {
    "de_DE": {
        "header": ["German (Germany)", "Example Language Services", "SAMPLE - invented content for testing", 1200,
                   "Usable output. Most edits were for informal address and glossary terms."],
        "rows": [
            ("Checkout page", "Your order ships within 2 business days.",
             "Ihre Bestellung wird innerhalb von 2 Geschäftstagen verschickt.",
             "Ihre Bestellung wird innerhalb von 2 Werktagen versendet.", "fluency", "Minor",
             "'Werktage' is the usual term for business days; 'versendet' matches the style guide."),
            ("", "Sign in to see your rewards", "Melden Sie sich an, um Ihre Belohnungen zu sehen",
             "Melde dich an, um deine Prämien zu sehen", "compliance", "Major",
             "Style guide requires informal 'du'. 'Prämien' is the glossary term for rewards."),
            ("", "{{count}} items in your cart", "{{count}} Artikel in Ihrem Warenkorb",
             "{{count}} Artikel in deinem Warenkorb", "compliance", "Minor", "Informal address, as above."),
            ("", "General issue", "", "", "compliance", "Major",
             "The glossary attached to the task has no German translations."),
        ],
    },
    "ja_JP": {
        "header": ["Japanese", "Example Language Services", "SAMPLE - invented content for testing", 800,
                   "Amount placeholders are misread and headings are too literal."],
        "rows": [
            ("Account pages", "Track your package", "あなたのパッケージを追跡する", "荷物を追跡", "fluency", "Major",
             "Too literal for a heading; パッケージ is unnatural for a parcel."),
            ("", "Free returns within 30 days", "30日以内の無料返品", "30日以内なら返品無料", "fluency", "Minor",
             "More natural as a selling point."),
            ("", "Pay {{amount}} {{currencyCode}} today", "今日 {{amount}} 個の {{currencyCode}} を支払う",
             "本日 {{amount}} {{currencyCode}} をお支払い", "accuracy", "Critical",
             "The amount is treated as a number of items (個)."),
        ],
    },
}


def make_form(locale, spec):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "AI Output Evaluation"
    ws["A1"] = "AI Human Evaluation Form - SAMPLE (invented content)"
    ws["A1"].font = Font(bold=True, size=14)
    for r, label in zip(range(7, 12), ["Language:", "Language Team:", "Project Name:", "Wordcount:",
                                      "Comment on Overall AI Quality"]):
        ws[f"A{r}"] = label
    for r, value in zip(range(7, 12), spec["header"]):
        ws[f"B{r}"] = value
    for c, label in enumerate(["Lokalise Task Name", "Source", "Target - Raw AI", "Corrected AI output",
                               "Primary Issue", "Severity", "Comments (optional)"], start=1):
        ws.cell(row=15, column=c, value=label).font = Font(bold=True)
    for r, (task, src, raw, corr, cat, sev, comment) in enumerate(spec["rows"], start=16):
        for c, value in enumerate([task, src, raw, corr, CATEGORIES[cat], sev, comment], start=1):
            ws.cell(row=r, column=c, value=value or None)
    os.makedirs(os.path.join(HERE, "forms"), exist_ok=True)
    wb.save(os.path.join(HERE, "forms", f"AI_Human_Evaluation_Form_Sample_{locale}.xlsx"))


EN = {"checkout": {"title": "Checkout", "ships": "Your order ships within 2 business days.", "cta": "Place order"},
      "account": {"signin": "Sign in to see your rewards", "cart_count": "{{count}} items in your cart"},
      "footer": {"help": "Need help? Contact us."}}
DE_RAW = {"checkout": {"title": "Kasse", "ships": "Ihre Bestellung wird innerhalb von 2 Geschäftstagen verschickt.",
                       "cta": "Bestellung aufgeben"},
          "account": {"signin": "Melden Sie sich an, um Ihre Belohnungen zu sehen",
                      "cart_count": "{{count}} Artikel in Ihrem Warenkorb"},
          "footer": {"help": "Brauchen Sie Hilfe? Kontaktieren Sie uns."}}
DE_FINAL = {"checkout": {"title": "Kasse", "ships": "Ihre Bestellung wird innerhalb von 2 Werktagen versendet.",
                         "cta": "Jetzt bestellen"},
            "account": {"signin": "Melde dich an, um deine Prämien zu sehen",
                        "cart_count": "{{count}} Artikel in deinem Warenkorb"},
            "footer": {"help": "Brauchst du Hilfe? Kontaktiere uns."}}

JA_UNITS = [("nav.track", "Track your package", "あなたのパッケージを追跡する", "荷物を追跡"),
            ("returns.banner", "Free returns within 30 days", "30日以内の無料返品", "30日以内なら返品無料"),
            ("checkout.cta", "Place order", "注文する", "注文する")]


def make_xliff(path, which):
    units = "\n".join(
        f'      <trans-unit id="{key}" resname="{key}">\n'
        f"        <source>{src}</source>\n"
        f"        <target>{raw if which == 'raw' else final}</target>\n"
        f"      </trans-unit>" for key, src, raw, final in JA_UNITS)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
                 '  <file source-language="en" target-language="ja" datatype="plaintext" original="sample">\n'
                 f"    <body>\n{units}\n    </body>\n  </file>\n</xliff>\n")


PAIRS = [
    ("checkout.ships", "de-DE", "Your order ships within 2 business days.",
     "Ihre Bestellung wird innerhalb von 2 Geschäftstagen verschickt.",
     "Ihre Bestellung wird innerhalb von 2 Werktagen versendet."),
    ("checkout.title", "de-DE", "Checkout", "Kasse", "Kasse"),
    ("nav.track", "ja", "Track your package", "あなたのパッケージを追跡する", "荷物を追跡"),
    ("checkout.cta", "ja", "Place order", "注文する", "注文する"),
    ("returns.banner", "fr-FR", "Free returns within 30 days", "Retours gratuits dans les 30 jours",
     "Retours gratuits sous 30 jours"),
    ("footer.help", "fr-FR", "Need help? Contact us.", "Besoin d'aide ? Contactez-nous.",
     "Besoin d'aide ? Contactez-nous."),
]


def main():
    for locale, spec in FORMS.items():
        make_form(locale, spec)
    exports = os.path.join(HERE, "exports")
    os.makedirs(exports, exist_ok=True)
    for name, data in (("en_source.json", EN), ("de_raw.json", DE_RAW), ("de_final.json", DE_FINAL)):
        with open(os.path.join(exports, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    make_xliff(os.path.join(exports, "ja_raw.xliff"), "raw")
    make_xliff(os.path.join(exports, "ja_final.xliff"), "final")
    with open(os.path.join(HERE, "pairs.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["key", "language", "source", "raw", "final"])
        writer.writerows(PAIRS)
    print("Sample files written to", HERE)


if __name__ == "__main__":
    main()
