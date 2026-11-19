"""Placeholder checks: placeholders, URLs, links and tags compared with the source, plus a client's own
rules for placeholders that already include some of their words (a preposition, an article).

No AI is involved: every result comes from a rule applied to the text, so it is the same every run.

Results are attached to each row as row["checks"], a list of dicts:
    text     "raw" (AI output), "final" or "source"
    level    "Error" (definitely wrong), "Check" (a person should confirm), "Source issue" (report to the
             client) or "Note" (an allowed change)
    check    short label, e.g. "Placeholders", "URL path", "Word before placeholder"
    message  what was found
    status   "Fixed in review", "Left in final", "Introduced in review", "No final text",
             "Report to client", "Changed in review" or "Allowed"
and row["placeholders"]: the placeholders, URLs, links and tags found in the source (or the AI output when
there is no source).
"""
import json
import os
import re
from collections import Counter

from .readers import InputError

NAME = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
_NAME_RE = re.compile(NAME)

# Every notation seen in forms and exports. {{name}}, the Lokalise editor's 1:name and the Lokalise
# universal [%1$s:name] are the same placeholder written three ways.
_PLACEHOLDER = re.compile(
    r"\{\{\s*(?P<curly>" + NAME + r")\s*\}\}"
    r"|\[%(?:\d+\$)?[sdif@]:(?P<lok>" + NAME + r")\]"
    r"|\[(?P<lokpos>%(?:\d+\$)?(?:\.\d+)?[sdif@])\]"
    r"|%\((?P<py>[A-Za-z_][A-Za-z0-9_]*)\)[sdif]"
    r"|(?P<printf>%(?:\d+\$)?(?:\.\d+)?[sdif@])(?![A-Za-z])"
    r"|1:(?P<editor>" + NAME + r")"
    r"|\{(?P<brace>[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)\}"
)
_BRACED = re.compile(r"\{+[^{}\n]{0,120}\}+")
_LOOKS_LIKE_NAME = re.compile(r"\s*[^\W\d][\w.]*\s*")
_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)\b[^<>]*>")
_URL_CHARS = r"[^\s<>\"'()\[\]]"
_MD_LINK = re.compile(r"\]\(\s*(" + _URL_CHARS + r"+)\s*\)")
_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
_BARE_URL = re.compile(r"(?:https?://|www\.)" + _URL_CHARS + r"+")
_PH_URL = re.compile(r"\{\{" + NAME + r"\}\}/" + _URL_CHARS + r"*")
_WORD_BEFORE = re.compile(r"([^\W\d_]+['’]?)\s*$")
_SUFFIX_AFTER = re.compile(r"['’]?[^\W\d_]+")

LEVELS = ("Error", "Check", "Source issue", "Note")


def _apos(text):
    return text.replace("’", "'")


def _base(code):
    return re.split(r"[-_]", (code or "").strip().lower())[0]

# =============================================================== reading the text


def _malformed(text):
    """Broken placeholders, e.g. {{name}, {name}}, {{{name}}} or a name that isn't valid ({{país}})."""
    found = []
    for m in _BRACED.finditer(text):
        whole = m.group(0)
        opens = len(whole) - len(whole.lstrip("{"))
        closes = len(whole) - len(whole.rstrip("}"))
        inner = whole[opens:len(whole) - closes]
        if opens == closes == 2:
            bad = not _NAME_RE.fullmatch(inner.strip())
        elif opens == closes == 1:
            bad = False                     # {0}, {name}, or ICU text such as {count, plural, ...}
        else:                               # {{name}, {name}}, {{{name}}}; not ICU endings such as {#}}
            bad = bool(_LOOKS_LIKE_NAME.fullmatch(inner))
        if bad:
            found.append((m.start(), m.end(), whole))
    return found


def placeholders(text):
    """[(start, end, key, display)] for every placeholder; key is (family, name)."""
    text = text or ""
    masked = list(text)
    for start, end, _w in _malformed(text):
        masked[start:end] = " " * (end - start)
    out = []
    for m in _PLACEHOLDER.finditer("".join(masked)):
        g = m.groupdict()
        if g["curly"] or g["lok"] or g["editor"]:
            name = g["curly"] or g["lok"] or g["editor"]
            key, display = ("named", name), "{{" + name + "}}"
        elif g["lokpos"] or g["printf"]:
            name = g["lokpos"] or g["printf"]
            key, display = ("positional", name), name
        elif g["py"]:
            key, display = ("python", g["py"]), f"%({g['py']})s"
        else:
            key, display = ("brace", g["brace"]), "{" + g["brace"] + "}"
        out.append((m.start(), m.end(), key, display))
    return out


def _canonical(text, found):
    """The text with every placeholder written one way, so links containing them compare equal."""
    out, pos = [], 0
    for start, end, _key, display in found:
        out.append(text[pos:start])
        out.append(display)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def links(text, found=None):
    """URLs and link targets: Markdown (text)(target), href="", bare URLs, and {{placeholder}}/path."""
    text = _canonical(text or "", placeholders(text) if found is None else found)
    taken, out = [], []
    for pattern in (_MD_LINK, _HREF, _PH_URL, _BARE_URL):
        for m in pattern.finditer(text):
            span = m.span(1) if pattern.groups else m.span()
            if any(a <= span[0] and span[1] <= b for a, b in taken):
                continue
            value = text[span[0]:span[1]].rstrip(".,;:!?")
            if value:
                taken.append(span)
                out.append(value)
    return out


def tags(text):
    """HTML tags by name: <b>, </b>, <br> (a self-closing <br/> counts as <br>)."""
    return [f"<{m.group(1)}{m.group(2).lower()}>" for m in _TAG.finditer(text or "")]

# =============================================================== rules


def load_rules(path):
    """Client placeholder rules from a JSON file (see config/placeholder_rules.example.json)."""
    if not path:
        return {"file": None, "source_language": "en", "rules": []}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise InputError(f"can't read the placeholder rules file {path}: {exc}")
    except ValueError as exc:
        raise InputError(f"{path} isn't valid JSON: {exc}")
    rules = []
    for i, raw in enumerate(data.get("rules") or []):
        label = raw.get("id") or f"rule {i + 1}"
        try:
            pattern = re.compile(raw["placeholders"])
            replaces = re.compile(raw["replaces"]) if raw.get("replaces") else None
        except KeyError:
            raise InputError(f"{path}: {label} needs a \"placeholders\" pattern")
        except re.error as exc:
            raise InputError(f"{path}: {label} has a pattern that isn't a valid regular expression: {exc}")
        level = raw.get("level", "Error")
        if level not in ("Error", "Check"):
            raise InputError(f"{path}: {label} has level \"{level}\"; use \"Error\" or \"Check\"")
        words = {k.lower(): {_apos(w).lower() for w in v} for k, v in (raw.get("not_before") or {}).items()
                 if not k.startswith("_")}
        rules.append({
            "id": label, "pattern": pattern, "replaces": replaces, "level": level,
            "includes": raw.get("includes", "these words"), "not_before": words,
            "no_suffix_after": {c.lower() for c in raw.get("no_suffix_after") or []},
            "check_source": raw.get("check_source", True),
            "message": raw.get("message") or "“{word}” before {placeholder}, which already includes {includes}",
            "suffix_message": raw.get("suffix_message")
            or "“{word}” added after {placeholder}, which already includes {includes}",
            "source_message": raw.get("source_message")
            or "The source has “{word}” before {placeholder}, which already includes {includes}. "
               "Ask the client to fix the source",
        })
    return {"file": path, "source_language": (data.get("source_language") or "en").lower(), "rules": rules}


def _words_for(rule, code):
    code = (code or "").lower().replace("_", "-")
    return rule["not_before"].get(code) or rule["not_before"].get(_base(code)) or set()


def _rule_issues(text, found, code, rules, source=False):
    issues = []
    for start, end, key, display in found:
        if key[0] != "named":
            continue
        for rule in rules["rules"]:
            if not rule["pattern"].search(key[1]):
                continue
            if source and not rule["check_source"]:
                continue
            words = _words_for(rule, rules["source_language"] if source else code)
            m = _WORD_BEFORE.search(text[max(0, start - 60):start])
            if words and m and _apos(m.group(1)).lower() in words:
                fields = {"word": m.group(1), "placeholder": display, "includes": rule["includes"]}
                if source:
                    issues.append(_issue("Source issue", "Word before placeholder",
                                         rule["source_message"].format(**fields), ("word", rule["id"], key, m.group(1).lower())))
                else:
                    issues.append(_issue(rule["level"], "Word before placeholder", rule["message"].format(**fields),
                                         ("word", rule["id"], key, m.group(1).lower())))
            code_l = (code or "").lower().replace("_", "-")
            if not source and (code_l in rule["no_suffix_after"] or _base(code) in rule["no_suffix_after"]):
                s = _SUFFIX_AFTER.match(text, end)
                if s:
                    fields = {"word": s.group(0), "placeholder": display, "includes": rule["includes"]}
                    issues.append(_issue(rule["level"], "Suffix after placeholder",
                                         rule["suffix_message"].format(**fields), ("suffix", rule["id"], key)))
    return issues

# =============================================================== comparing two texts


def _issue(level, check, message, key):
    return {"level": level, "check": check, "message": message, "_key": key}


def _times(n):
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


def _compare(ref, ref_found, text, found, rules, what="the source", level_url="Error"):
    """Placeholders, URL paths, links and tags in text compared with ref."""
    issues = []
    ref_keys = Counter(k for *_x, k, _d in ref_found)
    keys = Counter(k for *_x, k, _d in found)
    shown = {k: d for *_x, k, d in ref_found + found}
    missing = list((ref_keys - keys).elements())
    added = list((keys - ref_keys).elements())
    # A placeholder that a client rule allows in place of another (from {{x.name}} -> {{x.fromPhrase}}).
    for a in list(added):
        for rule in rules["rules"]:
            if not (rule["replaces"] and a[0] == "named" and rule["pattern"].search(a[1])):
                continue
            prefix = a[1].rsplit(".", 1)[0] if "." in a[1] else ""
            match = next((m for m in missing if m[0] == "named" and rule["replaces"].search(m[1])
                          and (m[1].rsplit(".", 1)[0] if "." in m[1] else "") == prefix), None)
            if match:
                missing.remove(match)
                added.remove(a)
                issues.append(_issue("Note", "Placeholders", f"{shown[a]} is used in place of {shown[match]}; it "
                                     f"includes {rule['includes']}", ("swap", a, match)))
                break
    if len(set(missing)) == 1 and len(set(added)) == 1 and missing[0] not in keys and added[0] not in ref_keys:
        issues.append(_issue("Error", "Placeholders", f"{shown[missing[0]]} was changed to {shown[added[0]]}",
                             ("changed", missing[0], added[0])))
    else:
        for k in dict.fromkeys(missing):
            msg = (f"{shown[k]} is missing" if not keys[k] else
                   f"{shown[k]} appears {_times(keys[k])}, but {_times(ref_keys[k])} in {what}")
            issues.append(_issue("Error", "Placeholders", msg, ("missing", k)))
        for k in dict.fromkeys(added):
            msg = (f"{shown[k]} isn't in {what}" if not ref_keys[k] else
                   f"{shown[k]} appears {_times(keys[k])}, but {_times(ref_keys[k])} in {what}")
            issues.append(_issue("Error", "Placeholders", msg, ("added", k)))

    ref_links, text_links = Counter(links(ref, ref_found)), Counter(links(text, found))
    gone, new = list((ref_links - text_links).elements()), list((text_links - ref_links).elements())
    pairs = []
    if len(gone) == 1 and len(new) == 1:
        pairs, gone, new = [(gone[0], new[0])], [], []
    for old, cur in pairs:
        url = old.startswith("{{")
        issues.append(_issue(level_url if url else "Check", "URL path" if url else "Link",
                             f"{old} was changed to {cur}", ("link", old, cur)))
    for old in gone:
        url = old.startswith("{{")
        issues.append(_issue(level_url if url else "Check", "URL path" if url else "Link",
                             f"{old} is missing", ("link-missing", old)))
    for cur in new:
        url = cur.startswith("{{")
        issues.append(_issue(level_url if url else "Check", "URL path" if url else "Link",
                             f"{cur} isn't in {what}", ("link-added", cur)))

    ref_tags, text_tags = Counter(tags(ref)), Counter(tags(text))
    for t, n in (ref_tags - text_tags).items():
        issues.append(_issue("Check", "Tags", f"{t} appears {_times(text_tags[t])}, but {_times(ref_tags[t])} in "
                             f"{what}" if text_tags[t] else f"{t} is missing", ("tag-missing", t)))
    for t, n in (text_tags - ref_tags).items():
        if not ref_tags[t]:
            issues.append(_issue("Check", "Tags", f"{t} isn't in {what}", ("tag-added", t)))
    return issues


def _target_issues(ref, text, code, rules):
    found = placeholders(text)
    issues = [_issue("Error", "Broken placeholder", f"{w} isn't a valid placeholder", ("malformed", w))
              for _s, _e, w in _malformed(text)]
    if ref is not None:
        issues += _compare(ref, placeholders(ref), text, found, rules)
    issues += _rule_issues(text, found, code, rules)
    return issues


def check_row(row, rules):
    """Checks for one row. Returns (issues, placeholders found)."""
    source = row.get("source") or ""
    raw = row.get("raw_measured", row.get("raw")) or ""
    final = row.get("final") or ""
    code = row.get("code") or ""
    ref = source if source.strip() else None
    base_text = source if ref is not None else raw
    found = [d for *_x, d in placeholders(base_text)] + links(base_text) + tags(base_text)

    out = []
    if ref is not None:
        for issue in _rule_issues(source, placeholders(source), code, rules, source=True):
            out.append({**issue, "text": "source", "status": "Report to client"})
    raw_issues = _target_issues(ref, raw, code, rules) if raw.strip() else []
    final_issues = _target_issues(ref, final, code, rules) if final.strip() else []
    if ref is None and raw.strip() and final.strip():
        for issue in _compare(raw, placeholders(raw), final, placeholders(final), rules, what="the AI output",
                              level_url="Check"):
            if issue["level"] != "Note":
                issue["level"] = "Check"
            out.append({**issue, "text": "final", "status": "Changed in review"})
    final_keys = {i["_key"] for i in final_issues}
    raw_keys = {i["_key"] for i in raw_issues}
    for issue in raw_issues:
        if issue["level"] == "Note":
            status = "Allowed"
        elif not final.strip():
            status = "No final text"
        else:
            status = "Left in final" if issue["_key"] in final_keys else "Fixed in review"
        out.append({**issue, "text": "raw", "status": status})
    for issue in final_issues:
        if issue["_key"] not in raw_keys:
            status = "Allowed" if issue["level"] == "Note" else "Introduced in review"
            out.append({**issue, "text": "final", "status": status})
    for issue in out:
        issue.pop("_key", None)
    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    out.sort(key=lambda i: (order[i["level"]], {"source": 0, "raw": 1, "final": 2}[i["text"]]))
    return out, list(dict.fromkeys(found))


def run_checks(rows, rules):
    """Adds row["checks"] and row["placeholders"] to every row."""
    for row in rows:
        row["checks"], row["placeholders"] = check_row(row, rules)
    return rows

# =============================================================== summary


def _errors(row, text=None, left=False):
    return [c for c in row.get("checks") or [] if c["level"] == "Error" and (text is None or c["text"] == text)
            and (not left or c["status"] in ("Left in final", "Introduced in review"))]


def row_counts(row):
    """Per-row figures used by the workbook: errors in the AI output, errors left in the final text,
    and source issues."""
    checks = row.get("checks") or []
    return (len(_errors(row, "raw")), len(_errors(row, left=True)),
            sum(1 for c in checks if c["level"] == "Source issue"))


def summarise_checks(rows):
    """Per language (in row order) and in total: items counted once each."""
    per = {}
    for row in rows:
        s = per.setdefault(row["language"], {"items": 0, "with_placeholders": 0, "ai_errors": 0, "fixed": 0,
                                             "left_in_final": 0, "source_issues": 0, "to_check": 0})
        checks = row.get("checks") or []
        s["items"] += 1
        s["with_placeholders"] += bool(row.get("placeholders"))
        raw_errors = _errors(row, "raw")
        s["ai_errors"] += bool(raw_errors)
        s["fixed"] += bool(raw_errors) and all(c["status"] == "Fixed in review" for c in raw_errors)
        s["left_in_final"] += bool(_errors(row, left=True))
        s["source_issues"] += any(c["level"] == "Source issue" for c in checks)
        s["to_check"] += any(c["level"] == "Check" for c in checks)
    total = {k: sum(s[k] for s in per.values()) for k in
             ("items", "with_placeholders", "ai_errors", "fixed", "left_in_final", "source_issues", "to_check")}
    return {"languages": per, "total": total}


def status_label(status, mode):
    """Status as shown to readers: forms call the final text the corrected text."""
    if mode == "forms":
        return {"Left in final": "Left in corrected text", "No final text": "No corrected text"}.get(status, status)
    return status


def text_label(text, mode):
    return {"raw": "AI output", "source": "Source"}.get(text, "Corrected" if mode == "forms" else "Final")


def default_rules_file(repo_root):
    path = os.path.join(repo_root, "data", "placeholder_rules.json")
    return path if os.path.isfile(path) else None
