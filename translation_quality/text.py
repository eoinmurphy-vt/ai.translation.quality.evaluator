"""Tokenisation, placeholders, per-segment measurement and change highlighting."""
import difflib
import re
import unicodedata

from .languages import LANGUAGE_NAMES, _base
from .ter import ter

# ---------------------------------------------------------------- placeholders
# Each placeholder counts as one token. {{name}} and Lokalise's on-screen copy form "1:name"
# are treated as the same placeholder, so a difference in how text was pasted is not an edit.
_NAMED_PLACEHOLDERS = [
    re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}"),   # {{name}}
    re.compile(r"1:([A-Za-z_][A-Za-z0-9_.]*)"),              # 1:name (copied from the Lokalise editor)
]
_OTHER_PLACEHOLDERS = (
    r"\[%[^\]\s]*\]"                               # Lokalise universal placeholders: [%s], [%1$s]
    r"|%\([A-Za-z_][A-Za-z0-9_]*\)[sdif]"          # %(name)s
    r"|%(?:\d+\$)?(?:\.\d+)?[sdif@](?![A-Za-z])"   # %s, %d, %1$s, %.2f
    r"|\{[A-Za-z0-9_.]+\}"                         # {0}, {name}
    r"|</?[A-Za-z][^<>]*>"                         # HTML / XML tags
)
_OTHER_RE = re.compile(_OTHER_PLACEHOLDERS)
_SENTINEL = re.compile("[^]*")


def _normalise(text):
    text = text or ""
    for pattern in _NAMED_PLACEHOLDERS:
        text = pattern.sub(lambda m: f" ph:{m.group(1)} ", text)
    text = _OTHER_RE.sub(lambda m: f" {m.group(0)} ", text)
    return unicodedata.normalize("NFC", text).lower()

# ---------------------------------------------------------------- tokens
_CJK = "぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ"
_THAI_CLUSTER = r"[ก-ะาำ฿-ๆ๏-๛][ัิ-ฺ็-๎]*"
_NUMBER = r"\d+(?:[.,]\d+)*"

_TOKENS = {
    "word": re.compile("[^]*|" + _NUMBER + r"|[^\W\d_]+(?:['’][^\W\d_]+)*|[^\s]"),
    "char": re.compile("[^]*|" + _NUMBER + "|[" + _CJK + "]|" + _THAI_CLUSTER
                       + r"|[A-Za-zÀ-ɏ]+(?:['’][A-Za-z]+)*|[^\s]"),
}

# Languages written without spaces between words are measured per character.
CHAR_LANGUAGES = {"ja", "zh", "th", "lo", "km", "my", "yue", "bo"}
_NO_SPACE_SCRIPT = re.compile("[฀-໿က-႟ក-៿" + _CJK + "]")


def tokenize(text, unit):
    return _TOKENS[unit].findall(_normalise(text))


def unit_for(language_code=None, texts=()):
    """'char' for languages written without spaces, else 'word'.

    Decided by the language code when it is known, otherwise by the script of `texts`.
    """
    base = _base(re.split(r"[-_]", language_code or "")[0])
    if base in CHAR_LANGUAGES:
        return "char"
    if base in LANGUAGE_NAMES:
        return "word"
    letters = [c for c in "".join(t or "" for t in texts) if c.isalpha()]
    if letters and sum(1 for c in letters if _NO_SPACE_SCRIPT.match(c)) / len(letters) > 0.3:
        return "char"
    return "word"


def _characters(text):
    return [c for c in _SENTINEL.sub("§", _normalise(text)) if not c.isspace()]


def _levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j - 1] + (a[i - 1] != b[j - 1]), prev[j] + 1, cur[j - 1] + 1)
        prev = cur
    return prev[-1]


def measure(raw, final, unit):
    """Edit counts for one segment, or None when either side is empty.

    Keys: added, removed, replaced, moves, edits, ref_len (tokens in final), ter,
    char_edits, ref_chars, char_rate.
    """
    if not (raw or "").strip() or not (final or "").strip():
        return None
    result = ter(tokenize(raw, unit), tokenize(final, unit))
    a, b = _characters(raw), _characters(final)
    result["ter"] = result["edits"] / result["ref_len"] if result["ref_len"] else 0.0
    result["char_edits"] = _levenshtein(a, b)
    result["ref_chars"] = len(b)
    result["char_rate"] = result["char_edits"] / len(b) if b else 0.0
    return result

# ---------------------------------------------------------------- change highlighting
_DISPLAY_PLACEHOLDER = (r"\{\{[^}]*\}\}|1:[A-Za-z_][A-Za-z0-9_.]*|" + _OTHER_PLACEHOLDERS)
_DISPLAY = {
    "word": re.compile(_DISPLAY_PLACEHOLDER + r"|\s+|" + _NUMBER + r"|[^\W\d_]+(?:['’][^\W\d_]+)*|[^\s]"),
    "char": re.compile(_DISPLAY_PLACEHOLDER + r"|\s+|" + _NUMBER + "|[" + _CJK + "]|" + _THAI_CLUSTER
                       + r"|[A-Za-zÀ-ɏ]+|[^\s]"),
}


SMALL_ISLAND = 2  # unchanged tokens between two edits that are folded into one change in the display


def diff_ops(raw, final, unit):
    """Raw-to-final changes as [(op, text)], op in 'equal', 'delete', 'insert'.

    Joining the 'equal' and 'insert' parts gives the final text; 'equal' and 'delete' give the raw text
    (up to whitespace and placeholder notation).
    """
    def key(tok):  # case-insensitive and placeholder-notation-insensitive, like the TER itself
        return _normalise(tok).strip() or " "

    a, b = _DISPLAY[unit].findall(raw or ""), _DISPLAY[unit].findall(final or "")
    matcher = difflib.SequenceMatcher(a=[key(t) for t in a], b=[key(t) for t in b], autojunk=False)
    codes = [list(c) for c in matcher.get_opcodes()]
    # In a heavy rewrite, a word or two left unchanged between edits makes the change hard to read
    # ("~~old~~new the ~~old~~new"). Fold such small islands into one replaced chunk.
    merged = True
    while merged:
        merged = False
        for k in range(1, len(codes) - 1):
            tag, i1, i2, _j1, _j2 = codes[k]
            if (tag == "equal" and codes[k - 1][0] != "equal" and codes[k + 1][0] != "equal"
                    and sum(1 for t in a[i1:i2] if t.strip()) <= SMALL_ISLAND):
                before, after = codes[k - 1], codes[k + 1]
                codes[k - 1:k + 2] = [["replace", before[1], after[2], before[3], after[4]]]
                merged = True
                break
    out = []

    def emit(op, text):
        if not text:
            return
        if out and out[-1][0] == op:
            out[-1] = (op, out[-1][1] + text)
        else:
            out.append((op, text))

    for tag, i1, i2, j1, j2 in codes:
        if tag == "equal":
            emit("equal", "".join(b[j1:j2]))
            continue
        removed, added = "".join(a[i1:i2]), "".join(b[j1:j2])
        if removed.strip():
            emit("delete", removed)
        if added.strip():
            emit("insert", added)
        elif added:
            emit("equal", added)
    return out
