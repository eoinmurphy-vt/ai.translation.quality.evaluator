"""Per-language totals, shared by the console summary, the JSON output and the HTML report."""

# Rule-of-thumb editing levels for a TER value (upper bound exclusive), used in the HTML report.
BANDS = [
    ("unchanged", "No edits", 0.0),
    ("light", "Light (under 10%)", 0.10),
    ("moderate", "Moderate (10–30%)", 0.30),
    ("heavy", "Heavy (30–50%)", 0.50),
    ("rewrite", "Close to retranslation (over 50%)", None),
]


def band(ter):
    """Band id for a TER value: unchanged, light, moderate, heavy or rewrite. None if not measured."""
    if ter is None:
        return None
    if ter == 0:
        return "unchanged"
    for band_id, _label, upper in BANDS[1:]:
        if upper is None or ter < upper:
            return band_id
    return "rewrite"


def summarise(rows):
    """{language: totals} in first-seen order."""
    out = {}
    for r in rows:
        s = out.setdefault(r["language"], {"unit": r["unit"], "rows": 0, "measured": 0, "unchanged": 0,
                                           "edits": 0, "ref_len": 0, "char_edits": 0, "ref_chars": 0,
                                           "bands": {b[0]: 0 for b in BANDS}})
        s["rows"] += 1
        m = r.get("metrics")
        if m:
            s["measured"] += 1
            s["unchanged"] += m["edits"] == 0
            s["bands"][band(m["ter"])] += 1
            for k in ("edits", "ref_len", "char_edits", "ref_chars"):
                s[k] += m[k]
    for s in out.values():
        s["ter"] = s["edits"] / s["ref_len"] if s["ref_len"] else None
        s["char_rate"] = s["char_edits"] / s["ref_chars"] if s["ref_chars"] else None
    return out


def pooled_char_rate(rows):
    edits = sum(r["metrics"]["char_edits"] for r in rows if r.get("metrics"))
    chars = sum(r["metrics"]["ref_chars"] for r in rows if r.get("metrics"))
    return edits / chars if chars else None
