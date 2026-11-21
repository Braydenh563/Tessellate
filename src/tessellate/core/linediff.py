"""The page's line diff, in Python, so a hunk the person skipped is skipped on the server too.

A port of the DOC-DIFF block in `frontend/js/documents-history.js` (`docDiffLines`,
`docDiffHunks`, `docDiffApply`), line for line. Why a port rather than difflib: the
Confirm card numbers its hunks from the page's diff, and the press sends those numbers
back (`ToolExecuteBody.skip_hunks`). Two diff models could split the same edit into
different hunks, and "skip hunk 2" would then skip a change nobody saw.
`tests/test_tool_consent.py` runs both on the same texts and compares.
"""

from __future__ import annotations

#: The same cap as `DOC_DIFF_MAX_CELLS`: past it a rewrite is "all removed, all added".
MAX_CELLS = 4_000_000


def _split(text: str | None) -> list[str]:
    value = "" if text is None else str(text)
    return [] if value == "" else value.split("\n")


def _lcs(a: list[str], b: list[str]) -> list[tuple[str, str]]:
    n, m = len(a), len(b)
    width = m + 1
    table = [0] * ((n + 1) * width)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            table[i * width + j] = (
                table[(i + 1) * width + j + 1] + 1
                if a[i] == b[j]
                else max(table[(i + 1) * width + j], table[i * width + j + 1])
            )
    ops: list[tuple[str, str]] = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j]:
            ops.append((" ", a[i]))
            i += 1
            j += 1
        elif table[(i + 1) * width + j] >= table[i * width + j + 1]:
            ops.append(("-", a[i]))
            i += 1
        else:
            ops.append(("+", b[j]))
            j += 1
    ops.extend(("-", text) for text in a[i:])
    ops.extend(("+", text) for text in b[j:])
    return ops


def lines(before: str | None, after: str | None) -> list[tuple[str, str]]:
    """`(op, text)` for every line of both texts: `" "` kept, `"-"` old only, `"+"` new only."""
    a, b = _split(before), _split(after)
    start = 0
    while start < len(a) and start < len(b) and a[start] == b[start]:
        start += 1
    end_a, end_b = len(a), len(b)
    while end_a > start and end_b > start and a[end_a - 1] == b[end_b - 1]:
        end_a -= 1
        end_b -= 1
    middle = _middle(a[start:end_a], b[start:end_b])
    return [(" ", t) for t in a[:start]] + middle + [(" ", t) for t in a[end_a:]]


def _middle(mid_a: list[str], mid_b: list[str]) -> list[tuple[str, str]]:
    """The changed middle; one side empty, or a rewrite too big to align, is all removed then all added."""
    if not mid_a or not mid_b or len(mid_a) * len(mid_b) > MAX_CELLS:
        return [("-", t) for t in mid_a] + [("+", t) for t in mid_b]
    return _lcs(mid_a, mid_b)


def hunks(ops: list[tuple[str, str]]) -> list[tuple[int, int]]:
    """`(from, to)` op indexes of each run of changed lines with no kept line inside it."""
    found: list[list[int]] = []
    current: list[int] | None = None
    for index, (op, _text) in enumerate(ops):
        if op == " ":
            current = None
            continue
        if current is None:
            current = [index, index]
            found.append(current)
        current[1] = index
    return [(start, end) for start, end in found]


def apply(before: str | None, after: str | None, skipped: set[int] | list[int]) -> tuple[str, int]:
    """`after` with the skipped hunks left as they were in `before`, and how many hunks there were."""
    ops = lines(before, after)
    found = hunks(ops)
    rejected: set[int] = set()
    for index, (start, end) in enumerate(found):
        if index in set(skipped):
            rejected.update(range(start, end + 1))
    out = [
        text
        for index, (op, text) in enumerate(ops)
        if op == " " or (op == "+" and index not in rejected) or (op == "-" and index in rejected)
    ]
    return "\n".join(out), len(found)
