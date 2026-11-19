"""Translation Edit Rate (TER) with phrase shifts.

A port of the tercom algorithm as implemented in sacreBLEU: greedy phrase shifts that reduce
the Levenshtein distance, then the remaining insertions, deletions and substitutions.
Each shift counts as one edit. Works on any token lists; tokenisation lives in text.py.
"""

MAX_SHIFT_SIZE = 10        # longest phrase that may be moved, in tokens
MAX_SHIFT_DIST = 50        # furthest a phrase may be moved, in tokens
MAX_SHIFT_CANDIDATES = 1000


def _edit_distance(hyp, ref):
    """Levenshtein distance with a trace of operations.

    Trace ops: ' ' match, 's' substitution, 'i' token only in hyp (removed by the editor),
    'd' token only in ref (added by the editor).
    """
    n, m = len(hyp), len(ref)
    dist = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dist[i][0] = i
    for j in range(1, m + 1):
        dist[0][j] = j
    for i in range(1, n + 1):
        h, row, prev = hyp[i - 1], dist[i], dist[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j - 1] + (0 if h == ref[j - 1] else 1), prev[j] + 1, row[j - 1] + 1)
    i, j, ops = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dist[i][j] == dist[i - 1][j - 1] + (0 if hyp[i - 1] == ref[j - 1] else 1):
            ops.append(" " if hyp[i - 1] == ref[j - 1] else "s")
            i -= 1
            j -= 1
        elif i > 0 and dist[i][j] == dist[i - 1][j] + 1:
            ops.append("i")
            i -= 1
        else:
            ops.append("d")
            j -= 1
    return dist[n][m], "".join(reversed(ops))


def _alignment(trace):
    pos_h = pos_r = -1
    hyp_err, ref_err, align = [], [], {}
    for op in trace:
        if op in (" ", "s"):
            pos_h += 1
            pos_r += 1
            align[pos_r] = pos_h
            err = 0 if op == " " else 1
            hyp_err.append(err)
            ref_err.append(err)
        elif op == "i":
            pos_h += 1
            hyp_err.append(1)
        else:
            pos_r += 1
            align[pos_r] = pos_h
            ref_err.append(1)
    return align, ref_err, hyp_err


def _perform_shift(words, start, length, target):
    if target < start:
        return words[:target] + words[start:start + length] + words[target:start] + words[start + length:]
    if target > start + length:
        return words[:start] + words[start + length:target] + words[start:start + length] + words[target:]
    return (words[:start] + words[start + length:length + target]
            + words[start:start + length] + words[length + target:])


def _shift_candidates(hyp, ref):
    n_h, n_r = len(hyp), len(ref)
    for start_h in range(n_h):
        for start_r in range(n_r):
            if abs(start_r - start_h) > MAX_SHIFT_DIST:
                continue
            length = 0
            while hyp[start_h + length] == ref[start_r + length] and length < MAX_SHIFT_SIZE:
                length += 1
                yield start_h, start_r, length
                if n_h == start_h + length or n_r == start_r + length:
                    break


def ter(hyp, ref):
    """Edit counts for turning token list `hyp` (raw AI) into `ref` (final text).

    Returns a dict: added, removed, replaced, moves, edits (their sum) and ref_len.
    TER = edits / ref_len.
    """
    cache = {}

    def distance(words):
        key = tuple(words)
        if key not in cache:
            cache[key] = _edit_distance(list(words), ref)
        return cache[key]

    moves, current, checked = 0, list(hyp), 0
    while True:
        score, trace = distance(current)
        align, ref_err, hyp_err = _alignment(trace)
        best = None
        for start_h, start_r, length in _shift_candidates(current, ref):
            if sum(hyp_err[start_h:start_h + length]) == 0 or sum(ref_err[start_r:start_r + length]) == 0:
                continue
            if start_h <= align.get(start_r, -99) < start_h + length:
                continue
            prev_idx = -1
            for offset in range(-1, length):
                if start_r + offset == -1:
                    idx = 0
                elif start_r + offset in align:
                    idx = align[start_r + offset] + 1
                else:
                    break
                if idx == prev_idx:
                    continue
                prev_idx = idx
                shifted = _perform_shift(current, start_h, length, idx)
                candidate = (score - distance(shifted)[0], length, -start_h, -idx, shifted)
                checked += 1
                if best is None or candidate[:4] > best[:4]:
                    best = candidate
            if checked >= MAX_SHIFT_CANDIDATES:
                break
        if best is None or checked >= MAX_SHIFT_CANDIDATES or best[0] <= 0:
            break
        moves += 1
        current = best[4]
    _, trace = distance(current)
    added, removed, replaced = trace.count("d"), trace.count("i"), trace.count("s")
    return {"added": added, "removed": removed, "replaced": replaced, "moves": moves,
            "edits": added + removed + replaced + moves, "ref_len": len(ref)}
