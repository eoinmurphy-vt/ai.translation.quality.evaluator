"""Command line: python evaluate.py <forms|compare|table|selftest> ..."""
import argparse
import json
import os
import sys
from datetime import datetime

from . import __version__
from .readers import InputError, compare_exports, load_layout, read_forms, read_pairs_table
from .stats import summarise
from .ter import ter
from .text import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LAYOUT_FILE = os.path.join(REPO_ROOT, "config", "form_layout.json")

EXAMPLES = """examples:
  python evaluate.py forms "data/Drop2 forms" --html
  python evaluate.py forms "data/Drop2 forms" --title "Drop 2 review" --notes data/drop2_findings.md
  python evaluate.py compare --raw data/de_raw.json --final data/de_final.json --lang de-DE --html
  python evaluate.py table data/pairs.xlsx -o output/batch_TER.xlsx
  python evaluate.py selftest
"""


def _print_summary(summary, rows_label):
    pct = lambda v: f"{v * 100:5.1f}%" if v is not None else "    - "
    print(f"\n  {'Language':<26}{rows_label:>7}{'Measured':>10}{'Unchanged':>11}{'TER':>9}{'Char rate':>11}")
    for lang, s in summary.items():
        print(f"  {lang[:25]:<26}{s['rows']:>7}{s['measured']:>10}{s['unchanged']:>11}"
              f"{pct(s['ter']):>9}{pct(s['char_rate']):>11}  ({s['unit']})")


def _default_output(mode):
    os.makedirs("output", exist_ok=True)
    return os.path.join("output", f"TER_{mode}_{datetime.now():%Y%m%d-%H%M}.xlsx")


def _write_json(path, rows, summary, extra=None):
    payload = {"tool_version": __version__, "summary": summary, "rows": rows, **(extra or {})}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)


def selftest():
    hyp = "THIS WEEK THE SAUDIS denied information published in the new york times".lower().split()
    ref = "SAUDI ARABIA denied THIS WEEK information published in the AMERICAN new york times".lower().split()
    t = ter(hyp, ref)
    ok1 = (t["edits"], t["ref_len"], t["moves"]) == (4, 13, 1)
    print(f"TER reference example (Snover et al. 2006): {t['edits']} edits / {t['ref_len']} words = "
          f"{t['edits'] / t['ref_len']:.3f}, expected 4 / 13 = 0.308 -> {'PASS' if ok1 else 'FAIL'}")
    tokens = tokenize("本日5,0001:currencyCodeをお支払い", "char")
    ok2 = "ph:currencycode" in tokens and "5,000" in tokens
    print(f"Placeholder and character tokenisation -> {'PASS' if ok2 else 'FAIL'}")
    return 0 if ok1 and ok2 else 1


def build_parser():
    p = argparse.ArgumentParser(
        prog="evaluate.py", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EXAMPLES,
        description="AI Translation Quality Evaluation: measures how much reviewers changed AI translations "
                    "(Translation Edit Rate) and writes an Excel workbook.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="mode", metavar="MODE")
    sub.required = True

    def common(sp):
        sp.add_argument("-o", "--output", help="Excel file to write (default: output/TER_<mode>_<date>.xlsx)")
        sp.add_argument("--json", help="also write the results as JSON to this file")
        sp.add_argument("--html", action="store_true",
                        help="also write an HTML report next to the workbook (same name, .html)")
        sp.add_argument("--html-output", metavar="FILE", help="write the HTML report to this file (implies --html)")
        sp.add_argument("--title", help="title of the HTML report (implies --html)")
        sp.add_argument("--notes", metavar="FILE",
                        help="Markdown file with written findings, shown at the top of the HTML report (implies --html)")
        sp.add_argument("--no-ai-note", action="store_true",
                        help="don't show the 'drafted with AI, AI can make mistakes' note with the findings "
                             "(use only when a person wrote them)")

    f = sub.add_parser("forms", help="evaluation forms with logged issues (.xlsx/.xlsm)",
                       description="Read AI Human Evaluation Forms and measure every logged segment.")
    f.add_argument("paths", nargs="+", help="form files, or folders containing them")
    f.add_argument("--layout", default=DEFAULT_LAYOUT_FILE if os.path.isfile(DEFAULT_LAYOUT_FILE) else None,
                   help="form layout JSON (default: config/form_layout.json)")
    common(f)

    c = sub.add_parser("compare", help="raw AI export vs final export, one language (job-level TER)",
                       description="Compare a raw AI export with the final export of the same language, key by key.")
    c.add_argument("--raw", required=True, help="export taken straight after AI translation (JSON, CSV, XLSX, XLIFF)")
    c.add_argument("--final", required=True, help="export taken after review sign-off (same format)")
    c.add_argument("--lang", required=True, help="target language code, e.g. de-DE, ja, zh-CN")
    c.add_argument("--source", help="optional source-language export, to show the source text")
    c.add_argument("--text-column", help="CSV/XLSX: column with the translation (name or number; default 2)")
    c.add_argument("--source-column", help="CSV/XLSX: column with the source text in --source (default 2)")
    c.add_argument("--unit", choices=("auto", "word", "char"), default="auto",
                   help="count words or characters (default: decided by language)")
    common(c)

    t = sub.add_parser("table", help="one sheet with key, language, raw and final columns",
                       description="Measure every row of a sheet with key, language, raw and final columns.")
    t.add_argument("table", help="CSV or Excel file")
    t.add_argument("--sheet", help="worksheet name (default: the first sheet)")
    common(t)

    sub.add_parser("selftest", help="check the TER implementation against the published example")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.mode == "selftest":
        return selftest()
    from .excel import write_forms_workbook, write_pairs_workbook  # openpyxl import only when needed

    out = args.output or _default_output(args.mode)
    want_html = args.html or args.html_output or args.title or args.notes
    html_out = args.html_output or os.path.splitext(out)[0] + ".html"
    for path in (out, html_out if want_html else None, args.json):
        if path and os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
    notes = None
    if args.notes:
        try:
            with open(args.notes, encoding="utf-8-sig") as fh:
                notes = fh.read()
        except OSError as exc:
            print(f"\nError: can't read the notes file {args.notes}: {exc}", file=sys.stderr)
            return 2
    levels, forms = [], None
    try:
        if args.mode == "forms":
            layout = load_layout(args.layout)
            print("Reading evaluation forms:")
            forms, rows = read_forms(args.paths, layout)
            levels = layout["severity_levels"]
            inputs = args.paths
            write_forms_workbook(forms, rows, out, levels, inputs)
            extra = {"forms": forms}
            label = "Items"
        elif args.mode == "compare":
            rows = compare_exports(args.raw, args.final, args.lang, args.source, args.unit,
                                   args.text_column, args.source_column)
            inputs = [f"raw: {args.raw}", f"final: {args.final}", f"language: {args.lang}"]
            write_pairs_workbook(rows, out, inputs)
            extra, label = {}, "Keys"
        else:
            rows = read_pairs_table(args.table, args.sheet)
            inputs = [args.table]
            write_pairs_workbook(rows, out, inputs)
            extra, label = {}, "Rows"
        if want_html:
            from .html_report import build_report, write_report
            page = build_report(rows, "forms" if args.mode == "forms" else "pairs", inputs, title=args.title,
                                notes=notes, forms=forms, severity_levels=levels, ai_note=not args.no_ai_note)
            write_report(html_out, page)
    except InputError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"\nError: can't write {exc.filename or out}. If it is open, close it and run again.", file=sys.stderr)
        return 2
    summary = summarise(rows)
    _print_summary(summary, label)
    if args.json:
        _write_json(args.json, rows, summary, {**extra, "mode": args.mode, "inputs": inputs,
                                               "severity_levels": levels, "created": datetime.now().isoformat(timespec="minutes")})
        print(f"\nJSON written to {args.json}")
    print(f"\nWorkbook written to {out}")
    if want_html:
        print(f"HTML report written to {html_out}")
        if notes:
            from .html_report import findings_warnings
            for warning in findings_warnings(notes, rows):
                print(f"Findings check: {warning}")
    if args.mode == "forms":
        print("Note: forms list only the segments reviewers logged, so this TER describes those segments, "
              "not the whole job.")
    return 0
