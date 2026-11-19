"""HTML report: one self-contained file that opens in any browser, with no internet connection needed.

It holds everything that can be produced from the data: headline counts, edit-rate and effort charts,
a scorecard, the severity and category breakdown (forms), reviewers' overall comments and every item
with its changes highlighted. Written findings can be added from a Markdown file (--notes).
"""
import html
import re
from datetime import datetime

from . import __version__
from .stats import BANDS, band, pooled_char_rate, summarise
from .text import diff_ops

MAX_ITEMS_PER_LANGUAGE = 400   # export comparisons can have thousands of segments
BAND_STATUS = {"unchanged": "good", "light": "good", "moderate": "warning", "heavy": "serious", "rewrite": "critical"}
BAND_SHORT = {"unchanged": "No edits", "light": "Light", "moderate": "Moderate", "heavy": "Heavy",
              "rewrite": "Close to retranslation"}


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


_PLACEHOLDER = re.compile(r"\{\{\s*[A-Za-z_][A-Za-z0-9_.]*\s*\}\}|1:[A-Za-z_][A-Za-z0-9_.]*")


def _text(value):
    """Escaped text with placeholders shown as chips."""
    value, out, pos = value or "", [], 0
    for m in _PLACEHOLDER.finditer(value):
        out.append(esc(value[pos:m.start()]))
        out.append(f'<span class="ph">{esc(m.group(0))}</span>')
        pos = m.end()
    out.append(esc(value[pos:]))
    return "".join(out).replace("\n", "<br>")


def _changes(raw, final, unit):
    parts = []
    for op, text in diff_ops(raw, final, unit):
        t = _text(text)
        parts.append(t if op == "equal" else f"<del>{t}</del>" if op == "delete" else f"<ins>{t}</ins>")
    return "".join(parts)


def _pct(value, digits=0):
    return "–" if value is None else f"{value * 100:.{digits}f}%"


def _anchor(language):
    return "lang-" + re.sub(r"[^a-z0-9]+", "-", language.lower()).strip("-")


def _status(ter):
    b = band(ter)
    if b is None:
        return '<span class="status none"><i></i>Not measured</span>'
    return f'<span class="status {BAND_STATUS[b]}"><i></i>{BAND_SHORT[b]}</span>'

# =============================================================== Markdown notes


def markdown(text):
    """Small, safe Markdown subset: headings, paragraphs, lists, quotes, bold, italics, code, links."""
    out, para, lst = [], [], []

    def inline(t):
        t = esc(t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
        t = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", t)
        return re.sub(r"\[([^\]]+)\]\(((?:https?://|mailto:)[^)\s]+)\)", r'<a href="\2">\1</a>', t)

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
        if lst:
            tag = lst[0]
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in lst[1:]) + f"</{tag}>")
            lst.clear()

    for line in (text or "").replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s:
            flush()
            continue
        heading = re.match(r"(#{1,3})\s+(.*)", s)
        bullet = re.match(r"[-*+]\s+(.*)", s)
        number = re.match(r"\d+[.)]\s+(.*)", s)
        if heading:
            flush()
            level = len(heading.group(1)) + 2
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif bullet or number:
            tag = "ul" if bullet else "ol"
            if para or (lst and lst[0] != tag):
                flush()
            if not lst:
                lst.append(tag)
            lst.append((bullet or number).group(1))
        elif s.startswith(">"):
            flush()
            out.append("<blockquote>" + inline(s.lstrip("> ")) + "</blockquote>")
        elif lst and line[:1] in (" ", "\t"):
            lst[-1] += " " + s
        else:
            if lst:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)

# =============================================================== charts


def _by_language(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["language"], []).append(r)
    return groups


def _ordered(stats):
    return sorted(stats, key=lambda lang: (stats[lang]["ter"] is None, -(stats[lang]["ter"] or 0)))


def _strip_chart(stats, groups):
    rows_html = []
    for lang in _ordered(stats):
        s = stats[lang]
        unit = "chars" if s["unit"] == "char" else "words"
        label = (f'<div class="slab"><span class="sname">{esc(lang)}</span>'
                 f'<span class="scount">n={s["measured"]} · {unit}</span></div>')
        if s["ter"] is None:
            rows_html.append(f'<div class="srow">{label}<div class="strack empty"><span>Nothing to measure'
                             f'</span></div><div class="sval muted">–</div></div>')
            continue
        measured = sorted((r for r in groups[lang] if r["metrics"]), key=lambda r: r["metrics"]["ter"])
        dense = " dense" if len(measured) > 40 else ""
        dots, prev, lane = [], None, 0
        for r in measured:
            t = min(r["metrics"]["ter"], 1.0)
            lane = (lane + 1) % 3 if prev is not None and t - prev < 0.035 else 0
            prev = t
            ref = f"form row {r['row']}" if "row" in r else f"key {r.get('key', '')}"
            src = r["source"] or r["final"]
            tip = (f"{esc(lang)} · {esc(ref)}<br><b>TER {_pct(r['metrics']['ter'])}</b>"
                   + (f" · {esc(r['severity'])}" if r.get("severity") else "")
                   + f"<br><span class='tsrc'>{esc(src[:90] + ('…' if len(src) > 90 else ''))}</span>")
            dots.append(f'<button class="dot{dense}" style="left:{t * 100:.2f}%;--off:{[0, -7, 7][lane]}px" '
                        f'data-tip="{esc(tip)}" aria-label="{esc(lang)}, {esc(ref)}: TER '
                        f'{_pct(r["metrics"]["ter"])}"></button>')
        tick_tip = (f"{esc(lang)}: TER {_pct(s['ter'], 1)} over {s['measured']} segment(s) "
                    f"({s['edits']} edits / {s['ref_len']} {unit})")
        rows_html.append(f'<div class="srow">{label}<div class="strack">{"".join(dots)}'
                         f'<span class="tick" style="left:{min(s["ter"], 1) * 100:.2f}%" data-tip="{esc(tick_tip)}">'
                         f'</span></div><div class="sval">{_pct(s["ter"])}</div></div>')
    axis = "".join(f'<span style="left:{v}%">{v}%{"+" if v == 100 else ""}</span>' for v in (0, 25, 50, 75, 100))
    return ('<div class="key"><span><i class="kdot"></i>One segment</span><span><i class="ktick"></i>'
            'Language TER (all its segments combined)</span></div>'
            f'<div class="strip">{"".join(rows_html)}<div class="srow axisrow"><div></div>'
            f'<div class="saxis">{axis}</div><div></div></div></div>'
            '<p class="bands">Rule of thumb: under 10% light edit · 10–30% moderate · 30–50% heavy · '
            'over 50% close to retranslation. Segments above 100% are drawn at 100%.</p>')


def _sev_class(severity, levels):
    if not severity:
        return "sn"
    return f"s{levels.index(severity)}" if severity in levels[:3] else "sx"


def _severity_bars(rows, levels):
    groups = _by_language(rows)
    names = levels + ["Other", "Not given"]
    counts = {}
    for lang, items in groups.items():
        c = {n: 0 for n in names}
        for r in items:
            sev = r.get("severity") or "Not given"
            c[sev if sev in levels else ("Other" if sev != "Not given" else "Not given")] += 1
        counts[lang] = c
    used = [n for n in names if any(c[n] for c in counts.values())]
    biggest = max((sum(c.values()) for c in counts.values()), default=1)
    def cls(name):
        return {"Other": "sx", "Not given": "sn"}.get(name) or _sev_class(name, levels)

    bars = []
    for lang in sorted(counts, key=lambda k: -sum(counts[k].values())):
        c, total = counts[lang], sum(counts[lang].values())
        segs = "".join(f'<span class="seg {cls(n)}" style="flex:{c[n]}" data-tip="{esc(lang)}: {c[n]} {esc(n)}">'
                       f'{"<span>" + str(c[n]) + "</span>" if c[n] >= 2 else ""}</span>' for n in used if c[n])
        bars.append(f'<div class="brow"><div class="blab">{esc(lang)}</div><div class="btrack">'
                    f'<div class="bar" style="width:{total / biggest * 100:.2f}%">{segs}</div>'
                    f'<span class="btot">{total}</span></div></div>')
    legend = "".join(f'<span class="lg"><i class="sw {cls(n)}"></i>{esc(n)}</span>' for n in used)
    return f'<div class="legend">{legend}</div><div class="bars">{"".join(bars)}</div>'


def _category_table(rows):
    groups = _by_language(rows)
    totals = {}
    for r in rows:
        totals[r.get("category") or "None given"] = totals.get(r.get("category") or "None given", 0) + 1
    cats = sorted(totals, key=lambda c: -totals[c])
    level = lambda n: 0 if n == 0 else 1 if n == 1 else 2 if n <= 3 else 3 if n <= 6 else 4
    body = []
    for lang, items in groups.items():
        c = {cat: sum(1 for r in items if (r.get("category") or "None given") == cat) for cat in cats}
        cells = "".join(f'<td class="h{level(c[cat])}">{c[cat] or "·"}</td>' for cat in cats)
        body.append(f'<tr><th scope="row">{esc(lang)}</th>{cells}<td class="tot">{len(items)}</td></tr>')
    head = "".join(f"<th>{esc(c)}</th>" for c in cats)
    foot = "".join(f"<td>{totals[c]}</td>" for c in cats)
    return (f'<div class="tblwrap"><table class="heat"><thead><tr><th></th>{head}<th>Total</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody><tfoot><tr><th scope="row">All languages</th>{foot}'
            f'<td>{len(rows)}</td></tr></tfoot></table></div>')


def _effort_bars(stats):
    used = [b for b in BANDS if any(s["bands"][b[0]] for s in stats.values())]
    bars = []
    for lang in _ordered(stats):
        s = stats[lang]
        if not s["measured"]:
            continue
        segs = []
        for band_id, label, _ in used:
            n = s["bands"][band_id]
            if n:
                share = n / s["measured"]
                inner = f"<span>{n}</span>" if share >= 0.08 else ""
                segs.append(f'<span class="seg b-{band_id}" style="flex:{n}" '
                            f'data-tip="{esc(lang)}: {n} segment(s), {esc(label)}">{inner}</span>')
        bars.append(f'<div class="brow"><div class="blab">{esc(lang)}</div><div class="btrack">'
                    f'<div class="bar full">{"".join(segs)}</div><span class="btot">{s["measured"]}</span></div></div>')
    legend = "".join(f'<span class="lg"><i class="sw b-{b}"></i>{esc(label)}</span>' for b, label, _ in used)
    return f'<div class="legend">{legend}</div><div class="bars">{"".join(bars)}</div>'

# =============================================================== tables and detail


def _sev_chips(items, levels):
    counts = {}
    for r in items:
        sev = r.get("severity") or ""
        counts[sev] = counts.get(sev, 0) + 1
    order = levels + sorted(k for k in counts if k not in levels)
    return " ".join(f'<span class="mini {_sev_class(k, levels)}" title="{esc(k or "No severity")}">{counts[k]}</span>'
                    for k in order if counts.get(k))


def _scorecard_forms(stats, forms, groups, levels):
    rows = []
    for lang in _ordered(stats):
        s, lf = stats[lang], [f for f in forms if f["language"] == lang]
        teams = ", ".join(sorted({f.get("team") for f in lf if f.get("team")}))
        words = ", ".join(str(f.get("word_count")) for f in lf if f.get("word_count"))
        not_given = '<span class="muted">Not given</span>'
        rows.append(f'<tr><th scope="row"><a href="#{_anchor(lang)}">{esc(lang)}</a></th><td class="num">{len(lf)}</td>'
                    f'<td>{esc(teams) if teams else not_given}</td>'
                    f'<td>{esc(words) if words else not_given}</td><td class="num">{s["rows"]}</td>'
                    f'<td class="chips">{_sev_chips(groups[lang], levels)}</td><td class="num">{_pct(s["ter"])}</td>'
                    f'<td>{_status(s["ter"])}</td><td class="num">{_pct(s["char_rate"])}</td></tr>')
    legend = " ".join(f'<span class="mini {_sev_class(l, levels)}">n</span> {esc(l)}' for l in levels[:3])
    return (f'<div class="tblwrap"><table class="score"><thead><tr><th>Language</th><th class="num">Forms</th>'
            f'<th>Reviewer team</th><th>Word count</th><th class="num">Items</th><th>By severity</th>'
            f'<th class="num">TER</th><th>Editing on logged segments</th><th class="num">Char. edits</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="fine">TER and character edit rate cover the logged segments only. Severity: {legend} '
            f'<span class="mini sn">n</span> none given.</p>')


def _scorecard_pairs(stats):
    rows = []
    for lang in _ordered(stats):
        s = stats[lang]
        share = s["unchanged"] / s["measured"] if s["measured"] else None
        rows.append(f'<tr><th scope="row"><a href="#{_anchor(lang)}">{esc(lang)}</a></th>'
                    f'<td class="num">{s["rows"]}</td><td class="num">{s["measured"]}</td>'
                    f'<td class="num">{s["unchanged"]}</td><td class="num">{_pct(share)}</td>'
                    f'<td class="num">{_pct(s["ter"], 1)}</td><td>{_status(s["ter"])}</td>'
                    f'<td class="num">{_pct(s["char_rate"], 1)}</td><td>{"characters" if s["unit"] == "char" else "words"}</td></tr>')
    return (f'<div class="tblwrap"><table class="score"><thead><tr><th>Language</th><th class="num">Segments</th>'
            f'<th class="num">Measured</th><th class="num">Unchanged</th><th class="num">% unchanged</th>'
            f'<th class="num">TER</th><th>Editing needed</th><th class="num">Char. edits</th><th>Counted in</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _item_card(r, levels, final_label):
    m = r["metrics"]
    head = []
    if "severity" in r:
        sev = r.get("severity") or "No severity"
        head.append(f'<span class="sev {_sev_class(r.get("severity"), levels)}"><i></i>{esc(sev)}</span>')
        if r.get("category"):
            head.append(f'<span class="cat">{esc(r["category"])}</span>')
    head.append(f'<span class="met">TER <b>{_pct(m["ter"])}</b> · chars {_pct(m["char_rate"])}</span>' if m
                else '<span class="met muted">Not measured</span>')
    ref = f'{r["file"]} · row {r["row"]}' if "row" in r else (r.get("key") or "")
    head.append(f'<span class="rowref">{esc(ref)}</span>')
    body = []
    if r.get("source"):
        body.append(f'<dt>Source</dt><dd class="src">{_text(r["source"])}</dd>')
    if m:
        raw = r.get("raw_measured", r["raw"])
        body.append(f'<dt class="v-chg">Changes</dt><dd class="v-chg tgt">{_changes(raw, r["final"], r["unit"])}</dd>'
                    f'<dt class="v-raw">Raw AI</dt><dd class="v-raw tgt">{_text(r["raw"])}</dd>'
                    f'<dt class="v-fin">{final_label}</dt><dd class="v-fin tgt">{_text(r["final"])}</dd>')
    if r.get("comment"):
        body.append(f'<dt>Reviewer</dt><dd class="cmt">{_text(r["comment"])}</dd>')
    if r.get("notes"):
        body.append(f'<dt>Note</dt><dd class="cmt muted">{esc("; ".join(r["notes"]))}</dd>')
    return f'<article class="item"><header>{"".join(head)}</header><dl>{"".join(body)}</dl></article>'


def _detail(stats, groups, forms, levels, mode):
    sections = []
    for lang in _ordered(stats):
        s, items = stats[lang], groups[lang]
        facts, comments = [], []
        if mode == "forms":
            for f in (x for x in forms if x["language"] == lang):
                facts.append(f'<span><b>Form</b> {esc(f["file"])}</span>')
                for key, label in (("team", "Team"), ("project", "Project"), ("word_count", "Words")):
                    if f.get(key):
                        facts.append(f'<span><b>{label}</b> {esc(f[key])}</span>')
                if f.get("overall_comment"):
                    who = f'<cite>{esc(f["file"])}</cite>' if sum(1 for x in forms if x["language"] == lang) > 1 else ""
                    comments.append(f"<blockquote>{_text(f['overall_comment'])}{who}</blockquote>")
            shown, note = items, ""
            if not comments:
                comments.append('<p class="muted">No overall comment was given.</p>')
        else:
            changed = sorted((r for r in items if r["metrics"] and r["metrics"]["edits"]),
                             key=lambda r: -r["metrics"]["ter"])
            missing = [r for r in items if not r["metrics"]]
            facts.append(f'<span><b>Segments</b> {s["rows"]}</span><span><b>Unchanged</b> {s["unchanged"]}</span>')
            shown = changed[:MAX_ITEMS_PER_LANGUAGE] + missing[:50]
            note = (f'<p class="muted">Showing the {min(len(changed), MAX_ITEMS_PER_LANGUAGE)} edited segment(s), most '
                    f'edited first. {s["unchanged"]} unchanged segment(s) are not shown.'
                    + (f" {len(changed) - MAX_ITEMS_PER_LANGUAGE} more edited segments are in the Excel workbook."
                       if len(changed) > MAX_ITEMS_PER_LANGUAGE else "") + "</p>")
        if s["ter"] is not None:
            facts.append(f'<span><b>TER</b> {_pct(s["ter"], 1)} · {s["edits"]} edits / {s["ref_len"]} '
                         f'{"chars" if s["unit"] == "char" else "tokens"}</span>')
        final_label = "Corrected" if mode == "forms" else "Final"
        cards = "".join(_item_card(r, levels, final_label) for r in shown)
        sections.append(
            f'<section class="lang" id="{_anchor(lang)}"><div class="lang-head"><h3>{esc(lang)}</h3>{_status(s["ter"])}'
            f'</div><div class="facts">{"".join(facts)}</div>'
            + (f'<h4>Reviewer comments</h4>{"".join(comments)}' if mode == "forms" else "")
            + f'<h4>{"Logged items" if mode == "forms" else "Edited segments"} ({len(shown)})</h4>{note}'
            f'<div class="items">{cards}</div></section>')
    nav = "".join(f'<a href="#{_anchor(l)}">{esc(l)} <span>{stats[l]["rows"]}</span></a>' for l in _ordered(stats))
    final_label = "Corrected" if mode == "forms" else "Final"
    return (f'<div class="toolbar"><nav class="langnav" aria-label="Jump to language">{nav}</nav>'
            '<div class="viewsw" role="radiogroup" aria-label="Text shown">'
            '<input type="radio" name="view" id="view-chg" value="chg" checked><label for="view-chg">Changes</label>'
            '<input type="radio" name="view" id="view-both" value="both"><label for="view-both">Raw + '
            f'{final_label.lower()}</label>'
            '<input type="radio" name="view" id="view-raw" value="raw"><label for="view-raw">Raw AI</label>'
            f'<input type="radio" name="view" id="view-fin" value="fin"><label for="view-fin">{final_label}</label>'
            f'</div></div><div class="langs" id="langs" data-view="chg">{"".join(sections)}</div>')

# =============================================================== page


METHOD = """<p><b>TER (Translation Edit Rate)</b> = (tokens added + removed + replaced + phrase moves) ÷ tokens in the
final text, using the shift-aware algorithm from tercom and sacreBLEU (phrases up to 10 tokens, moved up to 50
positions). Case is ignored. Each language's TER combines all its measured segments.</p>
<p><b>Tokens</b> are words and punctuation marks. Languages written without spaces (Japanese, Chinese, Thai, Lao,
Khmer, Burmese) are measured per character, so compare them with other languages on the character edit rate.
Numbers such as 10,000 count as one token. Placeholders and tags count as one token each; <code>{{name}}</code>
and Lokalise's on-screen form <code>1:name</code> are treated as the same.</p>
<p><b>Character edit rate</b> = character-level edit distance (spaces ignored) ÷ characters in the final text.</p>
<p><b>Changes</b> show removed text in red strikethrough and added text in green underline. One or two unchanged
words between edits are folded into the edit to keep heavy rewrites readable.</p>
<p>TER counts edits, not their importance: fixing a wrong amount counts the same as fixing a comma. Read it
alongside the reviewers' severity ratings and comments.</p>"""

FORMS_CAVEAT = ("These figures cover only the segments reviewers logged, usually the problem ones. They show how "
                "heavily those segments were rewritten, not the AI's quality across the whole job; compare full "
                "exports (compare mode) for that. Languages measured per character aren't directly comparable with "
                "the others.")


def _stats_line_forms(rows, levels, n_forms):
    parts = [f"<span><b>{len(rows)}</b> items logged</span>"]
    for i, lvl in enumerate(levels):
        n = sum(1 for r in rows if r.get("severity") == lvl)
        if n:
            parts.append(f'<span class="sev {_sev_class(lvl, levels)}"><i></i>{n} {esc(lvl)}</span>')
    none = sum(1 for r in rows if not r.get("severity"))
    if none:
        parts.append(f'<span class="sev sn"><i></i>{none} no severity</span>')
    measured = sum(1 for r in rows if r["metrics"])
    rate = pooled_char_rate(rows)
    if rate is not None:
        parts.append(f"<span><b>{_pct(rate)}</b> of characters changed in the {measured} measured segments</span>")
    parts.append(f"<span><b>{n_forms}</b> form{'s' if n_forms != 1 else ''}</span>")
    return "".join(parts)


def _stats_line_pairs(rows, stats):
    measured = [r for r in rows if r["metrics"]]
    unchanged = sum(1 for r in measured if r["metrics"]["edits"] == 0)
    parts = [f"<span><b>{len(rows)}</b> segments</span>",
             f"<span><b>{unchanged}</b> unchanged ({_pct(unchanged / len(measured) if measured else None)})</span>"]
    units = {s["unit"] for s in stats.values()}
    if len(units) == 1:
        e = sum(s["edits"] for s in stats.values())
        n = sum(s["ref_len"] for s in stats.values())
        parts.append(f"<span>Overall TER <b>{_pct(e / n if n else None, 1)}</b></span>")
    parts.append(f"<span><b>{_pct(pooled_char_rate(rows), 1)}</b> of characters changed</span>")
    return "".join(parts)


def build_report(rows, mode, inputs, title=None, notes=None, forms=None, severity_levels=None):
    """Full HTML page as a string. mode is 'forms' or 'pairs'."""
    levels = list(severity_levels or [])
    stats, groups = summarise(rows), _by_language(rows)
    n_lang = len(stats)
    created = datetime.now()
    title = title or "AI translation quality evaluation"
    if mode == "forms":
        eyebrow = f"Evaluation forms · {n_lang} language{'s' if n_lang != 1 else ''} · {created:%d %b %Y}"
        lede = (f"Generated from {len(forms)} evaluation form{'s' if len(forms) != 1 else ''}. Edit rates compare "
                "the raw AI output with each reviewer's corrected version, for the segments reviewers logged.")
        stats_line = _stats_line_forms(rows, levels, len(forms))
    else:
        eyebrow = f"Raw AI vs final · {n_lang} language{'s' if n_lang != 1 else ''} · {created:%d %b %Y}"
        lede = "The raw AI output compared with the final, reviewed text, segment by segment."
        stats_line = _stats_line_pairs(rows, stats)

    toc, sections = [], []
    if notes:
        toc.append(("findings", "Findings"))
        sections.append(f'<section id="findings"><div class="findings"><h2>Findings</h2>{markdown(notes)}</div></section>')
    toc.append(("ter", "Edit rates"))
    caveat = f'<p class="callout">{FORMS_CAVEAT}</p>' if mode == "forms" else ""
    sections.append(
        '<section id="ter"><div class="sec-head"><span class="eyebrow">Translation edit rate</span>'
        f'<h2>{"How much the logged segments had to change" if mode == "forms" else "How much the AI output had to change"}'
        '</h2><p>TER counts the edits (words added, removed, replaced or moved) needed to turn the raw AI output into '
        'the final version, divided by the length of the final version.</p></div>'
        f'<div class="panel"><h3>TER by language</h3>{_strip_chart(stats, groups)}</div>{caveat}</section>')
    toc.append(("scorecard", "Scorecard"))
    card = _scorecard_forms(stats, forms, groups, levels) if mode == "forms" else _scorecard_pairs(stats)
    sections.append('<section id="scorecard"><div class="sec-head"><span class="eyebrow">Scorecard</span>'
                    f'<h2>Language by language</h2></div>{card}</section>')
    if mode == "forms":
        toc.append(("profile", "Issue profile"))
        sections.append(
            '<section id="profile"><div class="sec-head"><span class="eyebrow">Issue profile</span>'
            '<h2>Severity, category and editing effort</h2><p>Severity and category as each reviewer assigned them.'
            '</p></div><div class="two"><div class="panel"><h3>Items logged, by severity</h3>'
            f'{_severity_bars(rows, levels)}</div><div class="panel"><h3>Items logged, by category</h3>'
            f'<p class="sub">Darker cells mean more items.</p>{_category_table(rows)}</div></div>'
            '<div class="panel" style="margin-top:16px"><h3>Editing effort per logged segment</h3>'
            f'<p class="sub">Share of each language\'s measured segments in each TER band.</p>{_effort_bars(stats)}'
            '</div></section>')
    else:
        toc.append(("effort", "Editing effort"))
        sections.append(
            '<section id="effort"><div class="sec-head"><span class="eyebrow">Editing effort</span>'
            '<h2>How segments split by amount of editing</h2><p>Each bar is one language\'s measured segments, '
            'split by their TER. The number at the end is the segment count.</p></div>'
            f'<div class="panel">{_effort_bars(stats)}</div></section>')
    toc.append(("detail", "Detail"))
    sections.append('<section id="detail"><div class="sec-head"><span class="eyebrow">Detail</span>'
                    f'<h2>{"Every logged item" if mode == "forms" else "Edited segments"}, by language</h2>'
                    '<p>Use the switch to show the changes, or the raw and final text in full.</p></div>'
                    f'{_detail(stats, groups, forms, levels, mode)}</section>')
    toc.append(("method", "Method"))
    inputs_html = "".join(f"<li><code>{esc(i)}</code></li>" for i in inputs)
    sections.append('<section id="method"><div class="sec-head"><span class="eyebrow">Method</span>'
                    f'<h2>How the numbers were calculated</h2></div><div class="method">{METHOD}'
                    f'<p><b>Inputs</b></p><ul>{inputs_html}</ul><p class="muted">Created {created:%d %b %Y %H:%M} '
                    f'by ai.translation.quality.evaluator v{__version__}.</p></div></section>')

    nav = "".join(f'<a href="#{a}">{esc(t)}</a>' for a, t in toc)
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="generator" content="ai.translation.quality.evaluator {__version__}">'
            f'<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">'
            f'<header class="top"><span class="eyebrow">{esc(eyebrow)}</span><h1>{esc(title)}</h1>'
            f'<p class="lede">{lede}</p><div class="stats">{stats_line}</div>'
            f'<nav class="toc" aria-label="Contents">{nav}</nav></header>'
            f'{"".join(sections)}</div><div id="tip" hidden></div><script>{JS}</script></body></html>\n')


def write_report(path, page):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)


CSS = """
:root{--bg:#f5f6f7;--surface:#fff;--ink:#15191d;--ink-2:#444c55;--muted:#6b737c;--line:#dde1e5;--line-2:#c9ced4;
--accent:#1f5fbf;--accent-wash:#e8effa;--series:#2a78d6;--grid:#e3e6e9;--quote:#f0f3f7;
--s0:#d03b3b;--s1:#ec835a;--s2:#fab219;--sx:#9aa0a6;--sn:#c4c8cc;--on-s0:#fff;--on-s1:#fff;--on-s2:#0b0b0b;--on-sx:#0b0b0b;--on-sn:#15191d;
--good:#0c7d0c;--warning:#b8860b;--serious:#d0602e;--critical:#c23434;
--b-unchanged:#c4c8cc;--b-light:#86b6ef;--b-moderate:#3987e5;--b-heavy:#256abf;--b-rewrite:#104281;
--on-b-unchanged:#15191d;--on-b-light:#0b0b0b;--on-b-moderate:#fff;--on-b-heavy:#fff;--on-b-rewrite:#fff;
--h1:#cde2fb;--h2:#86b6ef;--h3:#3987e5;--h4:#1c5cab;--h1-ink:#15191d;--h2-ink:#15191d;--h3-ink:#fff;--h4-ink:#fff;
--del-bg:#fde4e2;--del-ink:#8e1f1f;--ins-bg:#dbf2e2;--ins-ink:#0e5a2c;--ph-bg:#eef0f3;--ph-ink:#3d4650;
--f-sans:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,"Hiragino Sans","Yu Gothic UI",Meiryo,"Microsoft YaHei","PingFang SC","Malgun Gothic","Apple SD Gothic Neo","Leelawadee UI",Thonburi,sans-serif;
--f-mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1214;--surface:#171b1f;--ink:#e9ecef;--ink-2:#c2c8ce;
--muted:#929aa3;--line:#2a3036;--line-2:#39414a;--accent:#7fb0f5;--accent-wash:#1a2a40;--series:#3987e5;--grid:#262c32;--quote:#1c2228;
--sx:#6b7177;--sn:#4d5258;--on-sx:#e9ecef;--on-sn:#e9ecef;--good:#3cbf3c;--warning:#e0a92a;--serious:#ec835a;--critical:#ef6b6b;
--b-unchanged:#4d5258;--b-light:#184f95;--b-moderate:#2a78d6;--b-heavy:#5598e7;--b-rewrite:#9ec5f4;
--on-b-unchanged:#e9ecef;--on-b-light:#fff;--on-b-moderate:#fff;--on-b-heavy:#0b0b0b;--on-b-rewrite:#0b0b0b;
--h1:#13355f;--h2:#1c5cab;--h3:#3987e5;--h4:#86b6ef;--h1-ink:#e9ecef;--h2-ink:#fff;--h3-ink:#0b0b0b;--h4-ink:#0b0b0b;
--del-bg:#4a1f22;--del-ink:#ffb8b2;--ins-bg:#173d27;--ins-ink:#a4e6bb;--ph-bg:#232a31;--ph-ink:#c2cad2;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f-sans);font-size:15px;line-height:1.6}
.wrap{max-width:68rem;margin:0 auto;padding:40px max(16px,env(safe-area-inset-right,0px)) 72px max(16px,env(safe-area-inset-left,0px));display:grid;grid-template-columns:minmax(0,1fr);gap:52px}
.wrap>*,section,.langs,.lang,.items{min-width:0}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,.viewsw input:focus-visible+label{outline:2px solid var(--accent);outline-offset:2px}
h1,h2,h3,h4,h5{text-wrap:balance;line-height:1.25;margin:0}
h1{font-size:clamp(1.7rem,1.2rem + 2vw,2.4rem);font-weight:600;letter-spacing:-.015em}
h2{font-size:1.4rem;font-weight:600}h3{font-size:1.08rem;font-weight:600}
h4{font-size:.76rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
p{margin:0}.muted{color:var(--muted)}.fine{font-size:.8rem;color:var(--muted);margin-top:8px}
code{font-family:var(--f-mono);font-size:.9em}
.eyebrow{font-family:var(--f-mono);font-size:.76rem;letter-spacing:.04em;color:var(--muted);text-transform:uppercase}
.sec-head{display:grid;gap:8px;margin-bottom:18px}.sec-head p{color:var(--ink-2);max-width:70ch}
header.top{display:grid;gap:14px}.lede{color:var(--ink-2);font-size:1.04rem;max-width:70ch}
.stats{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:.92rem;color:var(--ink-2)}.stats b{color:var(--ink)}
.toc{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.88rem;padding-top:10px;border-top:1px solid var(--line)}
.toc a{text-decoration:none}.toc a:hover{text-decoration:underline}
.findings{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:24px clamp(16px,3vw,32px);display:grid;gap:12px;max-width:100%}
.findings p,.findings li{max-width:74ch}.findings ul,.findings ol{margin:0;padding-left:1.3em;display:grid;gap:8px}
.findings h3{font-size:1.15rem;margin-top:14px;padding-top:14px;border-top:1px solid var(--line)}
.findings h2+h3{margin-top:0;padding-top:0;border-top:0}
.findings h4{font-size:1rem;text-transform:none;letter-spacing:0;color:var(--ink);margin-top:6px}
.findings h5{font-size:.92rem;margin-top:4px}.findings blockquote{margin:0}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:20px clamp(14px,2.5vw,24px);display:grid;gap:14px;align-content:start;min-width:0}
.panel .sub{font-size:.84rem;color:var(--muted);margin-top:-8px}
.two{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,3fr);gap:16px}
@media (max-width:820px){.two{grid-template-columns:minmax(0,1fr)}}
.callout{border-left:3px solid var(--line-2);padding:4px 0 4px 14px;color:var(--ink-2);font-size:.9rem;max-width:74ch;margin-top:16px}
.sev,.status{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;font-weight:600;white-space:nowrap}
.sev i,.status i{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.sev.s0 i{background:var(--s0)}.sev.s1 i{background:var(--s1)}.sev.s2 i{background:var(--s2)}.sev.sx i{background:var(--sx)}.sev.sn i{background:var(--sn)}
.status.good i{background:var(--good)}.status.warning i{background:var(--warning)}.status.serious i{background:var(--serious)}
.status.critical i{background:var(--critical)}.status.none i{border:2px solid var(--sx)}
.mini{display:inline-block;min-width:22px;padding:0 6px;border-radius:4px;font:600 .74rem/1.6 var(--f-mono);text-align:center}
.mini.s0{background:var(--s0);color:var(--on-s0)}.mini.s1{background:var(--s1);color:var(--on-s1)}.mini.s2{background:var(--s2);color:var(--on-s2)}
.mini.sx{background:var(--sx);color:var(--on-sx)}.mini.sn{background:var(--sn);color:var(--on-sn)}
.strip{display:grid;gap:2px}
.srow{display:grid;grid-template-columns:minmax(96px,170px) 1fr 52px;align-items:center;gap:12px;min-height:40px}
.slab{display:grid;line-height:1.25;min-width:0}.sname{font-weight:500;font-size:.9rem;overflow-wrap:anywhere}
.scount{font:.72rem var(--f-mono);color:var(--muted)}
.strack{position:relative;height:36px;margin:0 6px;background:linear-gradient(var(--grid),var(--grid)) 0 0/1px 100% no-repeat,linear-gradient(var(--grid),var(--grid)) 25% 0/1px 100% no-repeat,linear-gradient(var(--grid),var(--grid)) 50% 0/1px 100% no-repeat,linear-gradient(var(--grid),var(--grid)) 75% 0/1px 100% no-repeat,linear-gradient(var(--grid),var(--grid)) 100% 0/1px 100% no-repeat}
.strack::after{content:"";position:absolute;left:0;right:0;top:50%;height:1px;background:var(--line)}
.strack.empty{display:flex;align-items:center;padding-left:10px;font-size:.8rem;color:var(--muted);font-style:italic}.strack.empty::after{display:none}
.dot{position:absolute;top:calc(50% + var(--off,0px));width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;background:var(--series);border:2px solid var(--surface);padding:0;cursor:pointer;z-index:2}
.dot.dense{opacity:.6}.dot::before{content:"";position:absolute;inset:-6px}.dot:hover,.dot:focus-visible{transform:scale(1.3);opacity:1}
.tick{position:absolute;top:4px;bottom:4px;width:3px;margin-left:-1.5px;border-radius:2px;background:var(--ink);z-index:1;cursor:help}
.tick::before{content:"";position:absolute;inset:0 -6px}
.sval{font:600 .95rem var(--f-mono);text-align:right}.axisrow{min-height:22px}
.saxis{position:relative;height:18px;margin:0 6px;font:.7rem var(--f-mono);color:var(--muted)}.saxis span{position:absolute;transform:translateX(-50%)}
.key,.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.8rem;color:var(--ink-2)}
.key span,.lg{display:inline-flex;align-items:center;gap:7px}
.kdot{width:10px;height:10px;border-radius:50%;background:var(--series)}.ktick{width:3px;height:14px;border-radius:2px;background:var(--ink)}
.bands{font:.74rem var(--f-mono);color:var(--muted)}
.sw{width:12px;height:12px;border-radius:3px;display:inline-block}
.bars{display:grid;gap:8px}.brow{display:grid;grid-template-columns:minmax(96px,150px) 1fr;gap:10px;align-items:center}
.blab{font-size:.86rem;font-weight:500;overflow-wrap:anywhere}
.btrack{display:flex;align-items:center;gap:8px;min-width:0;border-left:1px solid var(--line-2)}
.bar{display:flex;gap:2px;height:20px;min-width:6px}.bar.full{width:calc(100% - 44px)}
.seg{display:flex;align-items:center;padding-left:6px;font:600 .72rem var(--f-mono);min-width:3px;overflow:hidden}
.seg:last-child{border-radius:0 4px 4px 0}
.s0.seg,.sw.s0{background:var(--s0);color:var(--on-s0)}.s1.seg,.sw.s1{background:var(--s1);color:var(--on-s1)}
.s2.seg,.sw.s2{background:var(--s2);color:var(--on-s2)}.sx.seg,.sw.sx{background:var(--sx);color:var(--on-sx)}
.sn.seg,.sw.sn{background:var(--sn);color:var(--on-sn)}
.b-unchanged{background:var(--b-unchanged);color:var(--on-b-unchanged)}.b-light{background:var(--b-light);color:var(--on-b-light)}
.b-moderate{background:var(--b-moderate);color:var(--on-b-moderate)}.b-heavy{background:var(--b-heavy);color:var(--on-b-heavy)}
.b-rewrite{background:var(--b-rewrite);color:var(--on-b-rewrite)}
.btot{font:600 .82rem var(--f-mono);color:var(--ink-2)}
.tblwrap{overflow-x:auto;min-width:0;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line)}
thead th{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600;white-space:nowrap}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
.num{text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.score{min-width:760px}table.score th[scope=row] a{font-weight:600;text-decoration:none}.chips{white-space:nowrap}
table.heat td{text-align:center;font-family:var(--f-mono);font-weight:600;min-width:56px;border-left:2px solid var(--surface)}
table.heat thead th{white-space:normal;text-align:center}table.heat thead th:first-child{text-align:left}
table.heat tbody th{font-weight:500;white-space:nowrap}table.heat td.h0{color:var(--muted);font-weight:400}
table.heat td.h1{background:var(--h1);color:var(--h1-ink)}table.heat td.h2{background:var(--h2);color:var(--h2-ink)}
table.heat td.h3{background:var(--h3);color:var(--h3-ink)}table.heat td.h4{background:var(--h4);color:var(--h4-ink)}
table.heat td.tot,table.heat tfoot td{background:none;color:var(--ink)}
table.heat tfoot th,table.heat tfoot td{border-top:1px solid var(--line-2);border-bottom:0;font-weight:600}
.ph{font:.84em var(--f-mono);background:var(--ph-bg);color:var(--ph-ink);border-radius:4px;padding:0 4px;overflow-wrap:anywhere}
del{background:var(--del-bg);color:var(--del-ink);text-decoration:line-through;text-decoration-thickness:1px;border-radius:3px;padding:0 1px}
ins{background:var(--ins-bg);color:var(--ins-ink);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px;border-radius:3px;padding:0 1px}
.toolbar{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 20px}
.langnav{display:flex;flex-wrap:wrap;gap:6px}
.langnav a{font-size:.8rem;text-decoration:none;padding:3px 9px;border:1px solid var(--line-2);border-radius:999px;color:var(--ink-2);background:var(--surface)}
.langnav a span{font-family:var(--f-mono);color:var(--muted);margin-left:2px}.langnav a:hover{border-color:var(--accent);color:var(--accent)}
.viewsw{display:inline-flex;flex-wrap:wrap;border:1px solid var(--line-2);border-radius:8px;overflow:hidden;background:var(--surface)}
.viewsw input{position:absolute;opacity:0;pointer-events:none}
.viewsw label{font-size:.8rem;padding:5px 12px;cursor:pointer;color:var(--ink-2);border-left:1px solid var(--line-2)}
.viewsw label:first-of-type{border-left:0}.viewsw input:checked+label{background:var(--accent-wash);color:var(--accent);font-weight:600}
.langs{display:grid;gap:44px;padding-top:20px}
.lang{display:grid;gap:12px;scroll-margin-top:70px}
.lang-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;border-bottom:2px solid var(--ink);padding-bottom:8px}
.lang-head h3{font-size:1.25rem}
.facts{display:flex;flex-wrap:wrap;gap:4px 20px;font-size:.82rem;color:var(--ink-2)}
.facts b{font-weight:600;color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;margin-right:4px}
blockquote{margin:0;background:var(--quote);border-radius:8px;padding:12px 16px;font-size:.92rem;color:var(--ink-2);max-width:80ch}
blockquote cite{display:block;font-style:normal;font-size:.74rem;color:var(--muted);margin-top:6px}
.items{display:grid;gap:10px}
.item{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 16px 14px;min-width:0}
.item header{display:flex;flex-wrap:wrap;align-items:center;gap:4px 14px;padding-bottom:8px;margin-bottom:8px;border-bottom:1px dashed var(--line)}
.cat{font-size:.8rem;color:var(--ink-2)}.met{font:.78rem var(--f-mono);color:var(--ink-2)}.met b{color:var(--ink)}
.rowref{font:.72rem var(--f-mono);color:var(--muted);margin-left:auto;overflow-wrap:anywhere}
.item dl{display:grid;grid-template-columns:86px 1fr;gap:6px 14px;margin:0;font-size:.9rem}
.item dt{font:500 .7rem/2 var(--f-mono);color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.item dd{margin:0;min-width:0;overflow-wrap:anywhere}.item dd.src{color:var(--ink-2)}.item dd.tgt{font-size:.95rem}
.item dd.cmt{font-size:.86rem;color:var(--ink-2)}
#langs[data-view="chg"] .v-raw,#langs[data-view="chg"] .v-fin,#langs[data-view="raw"] .v-chg,#langs[data-view="raw"] .v-fin,
#langs[data-view="fin"] .v-chg,#langs[data-view="fin"] .v-raw,#langs[data-view="both"] .v-chg{display:none}
.method{font-size:.88rem;color:var(--ink-2);display:grid;gap:10px;max-width:80ch}.method ul{margin:0;padding-left:1.2em}
#tip{position:fixed;z-index:50;pointer-events:none;max-width:min(340px,calc(100vw - 32px));background:var(--ink);color:var(--bg);font-size:.8rem;line-height:1.45;padding:8px 10px;border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.18)}
#tip .tsrc{opacity:.8}[hidden]{display:none!important}
@media (max-width:560px){.wrap{gap:40px;padding-top:28px}.srow{grid-template-columns:84px 1fr 42px;gap:8px}
.item dl{grid-template-columns:1fr;gap:0}.item dt{margin-top:6px}.toolbar{position:static}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media print{.toolbar,#tip{display:none}.wrap{max-width:none}}
"""

JS = """(function(){var tip=document.getElementById("tip");
function place(x,y){var r=tip.getBoundingClientRect();var l=Math.min(Math.max(8,x+14),window.innerWidth-r.width-8);var t=y+16;
if(t+r.height>window.innerHeight-8)t=y-r.height-12;tip.style.left=l+"px";tip.style.top=Math.max(8,t)+"px";}
function show(el,x,y){tip.innerHTML=el.getAttribute("data-tip");tip.hidden=false;place(x,y);}
function hide(){tip.hidden=true;}
document.addEventListener("pointerover",function(e){var el=e.target.closest&&e.target.closest("[data-tip]");if(el)show(el,e.clientX,e.clientY);else hide();});
document.addEventListener("pointermove",function(e){if(!tip.hidden&&e.target.closest&&e.target.closest("[data-tip]"))place(e.clientX,e.clientY);});
document.addEventListener("focusin",function(e){var el=e.target.closest&&e.target.closest("[data-tip]");if(el){var r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.bottom);}else hide();});
document.addEventListener("focusout",hide);window.addEventListener("scroll",hide,{passive:true});
var langs=document.getElementById("langs");if(!langs)return;
document.querySelectorAll('input[name="view"]').forEach(function(r){r.addEventListener("change",function(){if(r.checked){langs.setAttribute("data-view",r.value);try{localStorage.setItem("tqe-view",r.value);}catch(err){}}});});
try{var v=localStorage.getItem("tqe-view");var i=v&&document.getElementById("view-"+v);if(i){i.checked=true;langs.setAttribute("data-view",v);}}catch(err){}
})();"""
