"""Reading evaluation forms, translation exports and prepared comparison tables."""
import copy
import csv
import json
import os
import warnings
import xml.etree.ElementTree as ET

import openpyxl
from openpyxl.utils import column_index_from_string

from .languages import code_from_filename, code_from_text, display_name
from .text import measure, unit_for

# Evaluation forms use Excel features openpyxl can't read (data validation lists, macros). They don't
# affect the cell values read here, so the warnings would only alarm users.
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

DEFAULT_LAYOUT = {
    "sheet": "AI Output Evaluation",
    "first_data_row": 16,
    "columns": {"task": "A", "source": "B", "raw": "C", "corrected": "D",
                "category": "E", "severity": "F", "comment": "G", "key": None},
    "header_cells": {"language": "B7", "team": "B8", "project": "B9",
                     "word_count": "B10", "overall_comment": "B11"},
    "severity_levels": ["Critical", "Major", "Minor"],
    "category_separator": " - ",
    # Language codes to replace after reading them, e.g. {"ja-US": "ja"} when a file named ..._JP_US holds Japanese.
    "language_overrides": {},
}

SPREADSHEET_EXT = (".xlsx", ".xlsm")


class InputError(Exception):
    """A problem with an input file that the user can fix."""


def load_layout(path=None):
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    if not path:
        return layout
    try:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
    except (OSError, ValueError) as exc:
        raise InputError(f"Can't read form layout {path}: {exc}") from exc
    for key, value in user.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(layout.get(key), dict):
            layout[key].update({k: v for k, v in value.items() if not k.startswith("_")})
        else:
            layout[key] = value
    return layout


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()

# =============================================================== evaluation forms


def find_form_files(paths):
    files = []
    for path in paths:
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if name.lower().endswith(SPREADSHEET_EXT) and not name.startswith("~$"):
                    files.append(os.path.join(path, name))
        elif os.path.isfile(path):
            files.append(path)
        else:
            raise InputError(f"Not found: {path}")
    if not files:
        raise InputError("No .xlsx or .xlsm evaluation forms found in: " + ", ".join(paths))
    return files


def _severity(value, levels):
    for level in levels:
        if value.lower() == level.lower():
            return level
    return value


def read_forms(paths, layout=None, log=print):
    """Read evaluation forms. Returns (forms, rows).

    forms: one dict per file (file, code, language, team, project, word_count, overall_comment).
    rows: one dict per logged item, with metrics (None when there is no segment text to compare).
    """
    layout = layout or load_layout()
    cols = {k: (column_index_from_string(v) if v else None) for k, v in layout["columns"].items()}
    overrides = {k.lower(): v for k, v in (layout.get("language_overrides") or {}).items() if not k.startswith("_")}
    forms, rows = [], []
    for path in find_form_files(paths):
        name = os.path.basename(path)
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except Exception as exc:  # corrupt file, wrong format, password protected
            log(f"  Skipped {name}: can't open it ({exc})")
            continue
        if layout["sheet"] not in wb.sheetnames:
            log(f"  Skipped {name}: no sheet called '{layout['sheet']}' (it has: {', '.join(wb.sheetnames)})")
            continue
        ws = wb[layout["sheet"]]
        header = {k: _text(ws[addr].value) if addr else "" for k, addr in layout["header_cells"].items()}
        code = code_from_filename(path) or code_from_text(header.get("language"))
        if code and code.lower() in overrides:
            code = overrides[code.lower()]
        language = display_name(code) if code else (header.get("language") or os.path.splitext(name)[0])

        def cell(r, field):
            c = cols.get(field)
            return _text(ws.cell(row=r, column=c).value) if c else ""

        items, task = [], ""
        for r in range(layout["first_data_row"], ws.max_row + 1):
            item = {f: cell(r, f) for f in cols}
            if not any(item[f] for f in ("source", "raw", "corrected", "category", "severity", "comment")):
                continue
            task = item["task"] or task
            notes, raw = [], item["raw"]
            if "\n" in raw and "\n" not in item["source"]:
                notes.append("Raw AI cell holds more than one output; the first line is measured")
                raw = raw.split("\n")[0]
            sep = layout.get("category_separator") or None
            items.append({
                "file": name, "code": code or "", "language": language, "row": r,
                "task": task, "key": item.get("key", ""), "source": item["source"],
                "raw": item["raw"], "raw_measured": raw, "final": item["corrected"],
                "severity": _severity(item["severity"], layout["severity_levels"]),
                "category": item["category"].split(sep)[0].strip() if sep else item["category"],
                "category_full": item["category"], "comment": item["comment"], "notes": notes,
            })
        unit = unit_for(code, [i["final"] for i in items])
        for item in items:
            item["unit"] = unit
            item["metrics"] = measure(item["raw_measured"], item["final"], unit)
            if item["metrics"] is None:
                item["notes"].append("No raw and corrected text to compare; not measured")
        details = {("language_entered" if k == "language" else k): v for k, v in header.items()}
        forms.append({**details, "file": name, "code": code or "", "language": language, "unit": unit,
                      "items": len(items)})
        rows.extend(items)
        log(f"  {name}: {language}, {len(items)} item(s)")
    if not forms:
        raise InputError("None of the files could be read as evaluation forms.")
    return forms, rows

# =============================================================== exports


def _flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}::{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}::{i}"))
    elif obj is not None:
        out[prefix] = str(obj)
    return out


def read_table(path, sheet=None):
    """(header, rows) from a CSV file or a worksheet of an .xlsx/.xlsm file."""
    if not os.path.isfile(path):
        raise InputError(f"Not found: {path}")
    if path.lower().endswith(SPREADSHEET_EXT):
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        if sheet and sheet not in wb.sheetnames:
            raise InputError(f"{path} has no sheet '{sheet}' (it has: {', '.join(wb.sheetnames)})")
        ws = wb[sheet] if sheet else wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        try:
            header = [_text(h) for h in next(it)]
        except StopIteration:
            raise InputError(f"{path} is empty")
        rows = [[_text(c) for c in row] for row in it]
        wb.close()
        return header, rows
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            raise InputError(f"{path} is empty")
        return header, [row for row in reader]


def _column_index(header, column, default):
    """Column given as a header name or 1-based number; default is a 0-based index."""
    if column is None:
        return default
    if str(column).isdigit():
        return int(column) - 1
    lowered = [h.lower() for h in header]
    if str(column).lower() in lowered:
        return lowered.index(str(column).lower())
    raise InputError(f"No column '{column}'. Columns are: {', '.join(header)}")


def _xliff(path):
    """(targets, sources) keyed by resname/id, for XLIFF 1.2 and 2.0."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise InputError(f"Can't read {path} as XLIFF: {exc}") from exc
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    targets, sources = {}, {}
    for unit in root.iter():
        if local(unit) not in ("trans-unit", "unit"):
            continue
        key = unit.get("resname") or unit.get("name") or unit.get("id")
        src = [("".join(e.itertext())) for e in unit.iter() if local(e) == "source"]
        tgt = [("".join(e.itertext())) for e in unit.iter() if local(e) == "target"]
        if key:
            sources[key] = " ".join(src).strip()
            targets[key] = " ".join(tgt).strip()
    return targets, sources


def read_export(path, text_column=None):
    """(texts, sources) keyed by string key.

    JSON: flat or nested key -> text (nested keys are joined with '::').
    CSV / XLSX: key in the first column, text in the second, or in `text_column` (name or number).
    XLIFF: target text; the source text comes back too.
    """
    if not os.path.isfile(path):
        raise InputError(f"Not found: {path}")
    low = path.lower()
    if low.endswith(".json"):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                return _flatten(json.load(fh)), {}
        except ValueError as exc:
            raise InputError(f"Can't read {path} as JSON: {exc}") from exc
    if low.endswith((".xliff", ".xlf")):
        return _xliff(path)
    header, rows = read_table(path)
    idx = _column_index(header, text_column, 1)
    return {row[0]: (row[idx] if idx < len(row) else "") for row in rows if row and row[0]}, {}


def compare_exports(raw_path, final_path, language, source_path=None, unit="auto",
                    text_column=None, source_column=None):
    """One row per key found in either export."""
    raw, raw_src = read_export(raw_path, text_column)
    final, final_src = read_export(final_path, text_column)
    sources = {**raw_src, **final_src}
    if source_path:
        src_texts, src_sources = read_export(source_path, source_column)
        sources.update(src_sources or src_texts)
    code = code_from_text(language) or language
    if unit == "auto":
        unit = unit_for(code, final.values())
    name = display_name(code)
    rows = []
    for key in list(final) + [k for k in raw if k not in final]:
        notes = []
        if key not in raw:
            notes.append("Missing from the raw AI export")
        if key not in final:
            notes.append("Missing from the final export")
        metrics = None if notes else measure(raw[key], final[key], unit)
        if metrics is None and not notes:
            notes.append("Empty text; not measured")
        rows.append({"language": name, "code": code, "key": key, "source": sources.get(key, ""),
                     "raw": raw.get(key, ""), "final": final.get(key, ""), "unit": unit,
                     "metrics": metrics, "notes": notes})
    if not any(r["metrics"] for r in rows):
        raise InputError("No key appears with text in both exports. Check that they are for the same "
                         "project and language, and that --text-column points at the translation.")
    return rows


_ALIASES = {
    "key": ("key", "key_id", "key_name", "id", "string_id"),
    "language": ("language", "lang", "locale", "target_language"),
    "raw": ("raw", "raw_ai", "ai", "mt", "ai_output", "target_-_raw_ai", "target_raw_ai"),
    "final": ("final", "corrected", "post_edited", "postedited", "pe", "reviewed", "corrected_ai_output"),
    "source": ("source", "en", "english", "source_text"),
}


def read_pairs_table(path, sheet=None):
    """Rows from a sheet with key, language, raw and final columns (source optional)."""
    header, data = read_table(path, sheet)
    norm = [h.lower().strip().replace(" ", "_") for h in header]
    idx = {}
    for field, names in _ALIASES.items():
        idx[field] = next((norm.index(n) for n in names if n in norm), None)
    missing = [f for f in ("key", "language", "raw", "final") if idx[f] is None]
    if missing:
        raise InputError(f"{path} needs columns key, language, raw and final. Missing: {', '.join(missing)}. "
                         f"Found: {', '.join(header)}")

    def get(row, field):
        i = idx[field]
        return row[i] if i is not None and i < len(row) else ""

    records = [r for r in data if any((c or "").strip() for c in r)]
    by_lang = {}
    for r in records:
        by_lang.setdefault(get(r, "language"), []).append(r)
    rows = []
    for lang, group in by_lang.items():
        code = code_from_text(lang) or lang
        unit = unit_for(code, [get(r, "final") for r in group])
        for r in group:
            metrics = measure(get(r, "raw"), get(r, "final"), unit)
            rows.append({"language": display_name(code) or lang, "code": code, "key": get(r, "key"),
                         "source": get(r, "source"), "raw": get(r, "raw"), "final": get(r, "final"),
                         "unit": unit, "metrics": metrics,
                         "notes": [] if metrics else ["Empty raw or final text; not measured"]})
    if not rows:
        raise InputError(f"{path} has no data rows.")
    return rows
