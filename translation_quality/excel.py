"""Excel workbook output: About, Summary, Segments (and Forms for evaluation forms).

Edit counts are written as values. Edits, TER, character edit rate and every Summary figure
are Excel formulas over those values, so each number can be traced and re-checked in Excel.
"""
from datetime import datetime

import openpyxl
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import __version__
from .text import diff_ops

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
CODE_FILL = PatternFill("solid", fgColor="EEF1F5")
RULE = Side(style="thin", color="C9CED4")
TOTAL_RULE = Side(style="thin", color="1F3A5F")


def _fold_whitespace_runs(ops):
    """Attach whitespace-only runs to a neighbour. openpyxl writes a lone ' ' run without
    xml:space="preserve", and Excel then refuses to open the whole workbook."""
    ops = [list(o) for o in ops]
    out = []
    for i, (op, text) in enumerate(ops):
        if text.strip():
            out.append([op, text])
            continue
        nxt = ops[i + 1] if i + 1 < len(ops) else None
        if out and out[-1][0] == "equal":
            out[-1][1] += text
        elif nxt is not None and nxt[0] == "equal":
            nxt[1] = text + nxt[1]
        elif out:
            out[-1][1] += text
        elif nxt is not None:
            nxt[1] = text + nxt[1]
    return [tuple(o) for o in out]


def _changes_cell(raw, final, unit):
    """Rich text: deletions red and struck through, insertions green and underlined."""
    blocks = []
    for op, text in _fold_whitespace_runs(diff_ops(raw, final, unit)):
        if op == "equal":
            font = InlineFont(rFont=FONT, sz=10)
        elif op == "delete":
            font = InlineFont(rFont=FONT, sz=10, color="C00000", strike=True)
        else:
            font = InlineFont(rFont=FONT, sz=10, color="00703C", u="single")
        blocks.append(TextBlock(font, text))
    return CellRichText(blocks) if blocks else ""


def _write_table(ws, columns, records):
    """columns: [(id, header, width, kind)]; kind in text, wrap, int, pct, rich.
    records: dicts of id -> value; a value may be a callable(row_number, letters) returning a formula."""
    letters = {cid: get_column_letter(i + 1) for i, (cid, *_rest) in enumerate(columns)}
    ws.append([c[1] for c in columns])
    for record in records:
        r = ws.max_row + 1
        ws.append([None] * len(columns))
        for i, (cid, _h, _w, kind) in enumerate(columns):
            value = record.get(cid, "")
            if callable(value):
                value = value(r, letters)
            cell = ws.cell(row=r, column=i + 1, value=value)
            cell.font = Font(name=FONT, size=10)
            cell.alignment = Alignment(wrap_text=kind in ("wrap", "rich"), vertical="top")
            cell.border = Border(bottom=RULE)
            if kind == "int":
                cell.number_format = "#,##0"
            elif kind == "pct":
                cell.number_format = "0.0%"
    for i, (cid, header, width, _k) in enumerate(columns):
        h = ws.cell(row=1, column=i + 1)
        h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        h.fill = HEAD_FILL
        h.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i + 1)].width = width
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(ws.max_row, 2)}"
    return letters


def _metric_values(metrics):
    """Segment-level values and formulas shared by both workbook types."""
    if not metrics:
        return {}
    return {
        "added": metrics["added"], "removed": metrics["removed"], "replaced": metrics["replaced"],
        "moves": metrics["moves"],
        "edits": lambda r, L: f"=SUM({L['added']}{r}:{L['moves']}{r})",
        "ref": metrics["ref_len"],
        "ter": lambda r, L: f'=IF({L["ref"]}{r}>0,{L["edits"]}{r}/{L["ref"]}{r},"")',
        "changed": lambda r, L: f'=IF({L["edits"]}{r}>0,"Yes","No")',
        "char_edits": metrics["char_edits"], "ref_chars": metrics["ref_chars"],
        "char_rate": lambda r, L: f'=IF({L["ref_chars"]}{r}>0,{L["char_edits"]}{r}/{L["ref_chars"]}{r},"")',
    }


METRIC_COLUMNS = [
    ("unit", "Unit", 7, "text"), ("added", "Added", 8, "int"), ("removed", "Removed", 8, "int"),
    ("replaced", "Replaced", 9, "int"), ("moves", "Moves", 7, "int"), ("edits", "Edits", 7, "int"),
    ("ref", "Tokens in final", 9, "int"), ("ter", "TER", 8, "pct"),
]
CHAR_COLUMNS = [
    ("char_edits", "Char edits", 8, "int"), ("ref_chars", "Chars in final", 9, "int"),
    ("char_rate", "Char edit rate", 9, "pct"), ("notes", "Notes", 32, "wrap"),
]


def _rng(sheet, letter, last):
    return f"{sheet}!${letter}$2:${letter}${max(last, 2)}"


def _style_summary(ws, columns, total_row, note):
    for i, (_cid, header, width, kind) in enumerate(columns):
        ws.column_dimensions[get_column_letter(i + 1)].width = width
    for row in ws.iter_rows(min_row=2, max_row=total_row):
        for cell, (_cid, _h, _w, kind) in zip(row, columns):
            cell.font = Font(name=FONT, size=10, bold=cell.row == total_row)
            cell.border = Border(top=TOTAL_RULE) if cell.row == total_row else Border(bottom=RULE)
            cell.alignment = Alignment(vertical="top", wrap_text=kind == "wrap")
            cell.number_format = {"int": "#,##0", "pct": "0.0%"}.get(kind, "General")
    for i, (_c, header, _w, _k) in enumerate(columns):
        h = ws.cell(row=1, column=i + 1, value=header)
        h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        h.fill = HEAD_FILL
        h.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "B2"
    n = total_row + 2
    ws.cell(row=n, column=1, value=note).font = Font(name=FONT, size=9, italic=True, color="52514E")
    ws.cell(row=n, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=n, start_column=1, end_row=n, end_column=len(columns))
    ws.row_dimensions[n].height = 42


def _languages(rows):
    seen = []
    for r in rows:
        if r["language"] not in [s[0] for s in seen]:
            seen.append((r["language"], r["unit"]))
    return seen


def _about(wb, title, intro, inputs):
    ws = wb.create_sheet("About", 0)
    ws["A1"] = title
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    lines = [("p", f"Created {datetime.now():%d %b %Y %H:%M} by ai.translation.quality.evaluator v{__version__}."),
             ("p", "Inputs: " + "; ".join(inputs)), ("h", "What this workbook contains")] + intro + [
        ("h", "What TER means"),
        ("p", "TER (Translation Edit Rate) = edits needed to turn the raw AI text into the final text, divided by "
              "the number of tokens in the final text. Edits = tokens added + removed + replaced + phrase moves."),
        ("p", "Rule of thumb: under 10% light edit; 10-30% moderate; 30-50% heavy; over 50% close to retranslation."),
        ("h", "How it is calculated"),
        ("p", "Shift-aware TER as in tercom and sacreBLEU (phrases up to 10 tokens, moved up to 50 positions), "
              "case-insensitive."),
        ("p", "Tokens are words and punctuation marks, except for languages written without spaces (Japanese, "
              "Chinese, Thai, Lao, Khmer, Burmese), which are measured per character. Numbers such as 10,000 count "
              "as one token. Compare those languages with others on the character edit rate."),
        ("p", "Placeholders and tags count as one token each. {{name}} and Lokalise's on-screen form 1:name are "
              "treated as the same, so differences in how text was pasted are not counted as edits."),
        ("p", "Character edit rate = character-level edit distance (spaces ignored) / characters in the final text."),
        ("p", "Edit counts (Added, Removed, Replaced, Moves, tokens, characters) are stored as values. Edits, TER, "
              "the character edit rate and every Summary figure are Excel formulas over them."),
        ("p", "Changes column: red struck-through text was removed from the raw AI output; green underlined text "
              "was added by the reviewer."),
    ]
    r = 3
    for kind, text in lines:
        c = ws.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, size=11 if kind == "h" else 10, bold=kind == "h")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "h":
            ws.row_dimensions[r].height = 22
        r += 1
    ws.column_dimensions["A"].width = 120


def _save(wb, path):
    wb.calculation.fullCalcOnLoad = True
    wb.active = wb.sheetnames.index("Summary")
    wb.save(path)

# =============================================================== evaluation forms


def write_forms_workbook(forms, rows, path, severity_levels, inputs):
    wb = openpyxl.Workbook()
    seg = wb.active
    seg.title = "Segments"
    columns = [
        ("language", "Language", 16, "text"), ("file", "Form file", 24, "wrap"), ("row", "Form row", 7, "int"),
        ("task", "Task / key", 20, "wrap"), ("source", "Source", 38, "wrap"), ("raw", "Raw AI", 38, "wrap"),
        ("final", "Corrected", 38, "wrap"), ("changes", "Changes (raw to corrected)", 42, "rich"),
        ("severity", "Severity", 10, "text"), ("category", "Category", 15, "wrap"),
        ("comment", "Reviewer comment", 42, "wrap"),
    ] + METRIC_COLUMNS + CHAR_COLUMNS
    columns = [(c[0], c[1].replace("Tokens in final", "Tokens in corrected").replace("Chars in final", "Chars in corrected"),
                c[2], c[3]) for c in columns]
    records = []
    for x in rows:
        rec = {"language": x["language"], "file": x["file"], "row": x["row"], "task": x["key"] or x["task"],
               "source": x["source"], "raw": x["raw"], "final": x["final"], "severity": x["severity"],
               "category": x["category"], "comment": x["comment"], "unit": x["unit"], "notes": "; ".join(x["notes"])}
        if x["metrics"]:
            rec["changes"] = _changes_cell(x["raw_measured"], x["final"], x["unit"])
            rec.update(_metric_values(x["metrics"]))
        records.append(rec)
    L = _write_table(seg, columns, records)
    last = seg.max_row

    fsheet = wb.create_sheet("Forms")
    fcols = [("file", "Form file", 34, "wrap"), ("language", "Language", 18, "text"), ("code", "Code", 8, "text"),
             ("language_entered", "Language as entered", 16, "wrap"), ("unit", "Unit", 7, "text"),
             ("team", "Team", 18, "wrap"), ("project", "Project", 30, "wrap"),
             ("word_count", "Word count", 12, "text"), ("overall_comment", "Overall comment", 70, "wrap"),
             ("items", "Items logged", 9, "int")]
    frecs = []
    for f in forms:
        rec = {k: f.get(k, "") for k, *_ in fcols}
        rec["items"] = lambda r, FL: f"=COUNTIF({_rng('Segments', L['file'], last)},{FL['file']}{r})"
        frecs.append(rec)
    FL = _write_table(fsheet, fcols, frecs)
    flast = fsheet.max_row

    summ = wb.create_sheet("Summary", 0)
    scols = ([("language", "Language", 22, "text"), ("unit", "Unit", 7, "text"), ("forms", "Forms", 7, "int"),
              ("items", "Items logged", 9, "int")]
             + [(f"sev{i}", lvl, 9, "int") for i, lvl in enumerate(severity_levels)]
             + [("sev_other", "Other / no severity", 10, "int"), ("measured", "Segments measured", 10, "int"),
                ("edits", "Edits", 8, "int"), ("ref", "Tokens in corrected", 11, "int"),
                ("ter", "TER (logged segments)", 12, "pct"), ("char_edits", "Char edits", 9, "int"),
                ("ref_chars", "Chars in corrected", 11, "int"), ("char_rate", "Char edit rate", 10, "pct")])
    S = {cid: get_column_letter(i + 1) for i, (cid, *_r) in enumerate(scols)}
    seg_rng = lambda cid: _rng("Segments", L[cid], last)
    summ.append([c[1] for c in scols])
    langs = _languages(rows)
    for lang, unit in langs:
        r = summ.max_row + 1
        a = f"$A{r}"
        values = {"language": lang, "unit": unit,
                  "forms": f"=COUNTIF({_rng('Forms', FL['language'], flast)},{a})",
                  "items": f"=COUNTIF({seg_rng('language')},{a})"}
        for i, lvl in enumerate(severity_levels):
            values[f"sev{i}"] = f'=COUNTIFS({seg_rng("language")},{a},{seg_rng("severity")},"{lvl}")'
        values["sev_other"] = f"={S['items']}{r}-" + "-".join(f"{S[f'sev{i}']}{r}" for i in range(len(severity_levels)))
        values.update({
            "measured": f'=COUNTIFS({seg_rng("language")},{a},{seg_rng("ref")},">0")',
            "edits": f"=SUMIFS({seg_rng('edits')},{seg_rng('language')},{a})",
            "ref": f"=SUMIFS({seg_rng('ref')},{seg_rng('language')},{a})",
            "ter": f'=IF({S["ref"]}{r}>0,{S["edits"]}{r}/{S["ref"]}{r},"")',
            "char_edits": f"=SUMIFS({seg_rng('char_edits')},{seg_rng('language')},{a})",
            "ref_chars": f"=SUMIFS({seg_rng('ref_chars')},{seg_rng('language')},{a})",
            "char_rate": f'=IF({S["ref_chars"]}{r}>0,{S["char_edits"]}{r}/{S["ref_chars"]}{r},"")',
        })
        summ.append([values.get(cid, "") for cid, *_ in scols])
    first, lastl = 2, summ.max_row
    t = lastl + 1
    total = {"language": "All languages", "unit": "mixed" if len({u for _, u in langs}) > 1 else langs[0][1]}
    for cid in ["forms", "items", "sev_other", "measured", "char_edits", "ref_chars"] + [f"sev{i}" for i in range(len(severity_levels))]:
        total[cid] = f"=SUM({S[cid]}{first}:{S[cid]}{lastl})"
    if total["unit"] == "mixed":
        total.update({"edits": "", "ref": "", "ter": "n/a (mixed units)"})
    else:
        total.update({"edits": f"=SUM({S['edits']}{first}:{S['edits']}{lastl})",
                      "ref": f"=SUM({S['ref']}{first}:{S['ref']}{lastl})",
                      "ter": f'=IF({S["ref"]}{t}>0,{S["edits"]}{t}/{S["ref"]}{t},"")'})
    total["char_rate"] = f'=IF({S["ref_chars"]}{t}>0,{S["char_edits"]}{t}/{S["ref_chars"]}{t},"")'
    summ.append([total.get(cid, "") for cid, *_ in scols])
    _style_summary(summ, scols, t,
                   "TER here covers only the segments reviewers logged on the forms, usually their problem segments. "
                   "It shows how heavily those were rewritten, not the AI's quality across the whole job; for that, "
                   "compare full exports (see About). Languages measured per character are best compared on the "
                   "character edit rate.")
    _about(wb, "AI Translation Quality Evaluation: evaluation forms", [
        ("p", "Summary: items logged, severity and edit rates per language."),
        ("p", "Segments: every item logged on the forms, with raw AI text, corrected text, the changes between "
              "them and their edit counts. Items without both texts (general comments) are listed but not measured."),
        ("p", "Forms: the header details of each form (team, project, word count, overall comment)."),
    ], inputs)
    _save(wb, path)

# =============================================================== export comparison


def write_pairs_workbook(rows, path, inputs):
    wb = openpyxl.Workbook()
    seg = wb.active
    seg.title = "Segments"
    columns = ([("language", "Language", 16, "text"), ("key", "Key", 30, "wrap"), ("source", "Source", 38, "wrap"),
                ("raw", "Raw AI", 38, "wrap"), ("final", "Final", 38, "wrap"),
                ("changes", "Changes (raw to final)", 42, "rich")]
               + METRIC_COLUMNS + [("changed", "Changed?", 9, "text")] + CHAR_COLUMNS)
    records = []
    for x in rows:
        rec = {"language": x["language"], "key": x["key"], "source": x["source"], "raw": x["raw"],
               "final": x["final"], "unit": x["unit"], "notes": "; ".join(x["notes"])}
        if x["metrics"]:
            if x["metrics"]["edits"]:
                rec["changes"] = _changes_cell(x["raw"], x["final"], x["unit"])
            rec.update(_metric_values(x["metrics"]))
        records.append(rec)
    L = _write_table(seg, columns, records)
    last = seg.max_row
    seg_rng = lambda cid: _rng("Segments", L[cid], last)

    summ = wb.create_sheet("Summary", 0)
    scols = [("language", "Language", 22, "text"), ("unit", "Unit", 7, "text"), ("segments", "Segments", 9, "int"),
             ("measured", "Measured", 9, "int"), ("unchanged", "Unchanged", 10, "int"),
             ("pct_unchanged", "% unchanged", 10, "pct"), ("edits", "Edits", 9, "int"),
             ("ref", "Tokens in final", 10, "int"), ("ter", "TER (job level)", 11, "pct"),
             ("char_edits", "Char edits", 9, "int"), ("ref_chars", "Chars in final", 10, "int"),
             ("char_rate", "Char edit rate", 10, "pct")]
    S = {cid: get_column_letter(i + 1) for i, (cid, *_r) in enumerate(scols)}
    summ.append([c[1] for c in scols])
    langs = _languages(rows)
    for lang, unit in langs:
        r = summ.max_row + 1
        a = f"$A{r}"
        values = {
            "language": lang, "unit": unit,
            "segments": f"=COUNTIF({seg_rng('language')},{a})",
            "measured": f'=COUNTIFS({seg_rng("language")},{a},{seg_rng("ref")},">0")',
            "unchanged": f'=COUNTIFS({seg_rng("language")},{a},{seg_rng("changed")},"No")',
            "pct_unchanged": f'=IF({S["measured"]}{r}>0,{S["unchanged"]}{r}/{S["measured"]}{r},"")',
            "edits": f"=SUMIFS({seg_rng('edits')},{seg_rng('language')},{a})",
            "ref": f"=SUMIFS({seg_rng('ref')},{seg_rng('language')},{a})",
            "ter": f'=IF({S["ref"]}{r}>0,{S["edits"]}{r}/{S["ref"]}{r},"")',
            "char_edits": f"=SUMIFS({seg_rng('char_edits')},{seg_rng('language')},{a})",
            "ref_chars": f"=SUMIFS({seg_rng('ref_chars')},{seg_rng('language')},{a})",
            "char_rate": f'=IF({S["ref_chars"]}{r}>0,{S["char_edits"]}{r}/{S["ref_chars"]}{r},"")',
        }
        summ.append([values.get(cid, "") for cid, *_ in scols])
    first, lastl = 2, summ.max_row
    t = lastl + 1
    mixed = len({u for _, u in langs}) > 1
    total = {"language": "All languages", "unit": "mixed" if mixed else langs[0][1]}
    for cid in ("segments", "measured", "unchanged", "char_edits", "ref_chars"):
        total[cid] = f"=SUM({S[cid]}{first}:{S[cid]}{lastl})"
    total["pct_unchanged"] = f'=IF({S["measured"]}{t}>0,{S["unchanged"]}{t}/{S["measured"]}{t},"")'
    if mixed:
        total.update({"edits": "", "ref": "", "ter": "n/a (mixed units)"})
    else:
        total.update({"edits": f"=SUM({S['edits']}{first}:{S['edits']}{lastl})",
                      "ref": f"=SUM({S['ref']}{first}:{S['ref']}{lastl})",
                      "ter": f'=IF({S["ref"]}{t}>0,{S["edits"]}{t}/{S["ref"]}{t},"")'})
    total["char_rate"] = f'=IF({S["ref_chars"]}{t}>0,{S["char_edits"]}{t}/{S["ref_chars"]}{t},"")'
    summ.append([total.get(cid, "") for cid, *_ in scols])
    _style_summary(summ, scols, t,
                   "TER (job level) covers every key found in both exports, including unchanged ones. Keys missing "
                   "from either export are listed on Segments with a note and are not counted. Languages measured per "
                   "character are best compared with others on the character edit rate.")
    _about(wb, "AI Translation Quality Evaluation: raw AI vs final", [
        ("p", "Summary: job-level TER per language and the share of segments left unchanged."),
        ("p", "Segments: every key, with source, raw AI and final text, the changes between them and edit counts."),
    ], inputs)
    _save(wb, path)
