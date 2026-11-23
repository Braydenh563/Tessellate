"""The zero-specificity guard a moved rule carries.

A boot rule moved to library-lazy.css (L-ui-modernisation-51) keeps losing to the boot rule it lost to by
ending in `:where(:not(...))`, which names the other elements and never the rule's own subject. A test that
reads a rule by its selector reads the subject, as it did before the move.

Not named `test_*.py` on purpose: pytest would otherwise try to collect it.
"""

from __future__ import annotations

import re

KEY = ":where(:not("


def unwrap_all(css: str) -> str:
    """Text with every `:where(:not(...))` group removed (balanced parentheses)."""
    out, i = [], 0
    while i < len(css):
        if css.startswith(KEY, i):
            depth, j = 2, i + len(KEY)
            while j < len(css) and depth:
                depth += (css[j] == "(") - (css[j] == ")")
                j += 1
            i = j
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def unwrap(selector: str) -> str:
    """One selector without its guard groups, whitespace collapsed."""
    return re.sub(r"\s+", " ", unwrap_all(selector)).strip()


def split_top(selector: str) -> list[str]:
    """A selector list split at its top-level commas, each part unwrapped."""
    parts, depth, cur = [], 0, ""
    for ch in selector:
        depth += {"(": 1, ")": -1, "[": 1, "]": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(unwrap(cur))
            cur = ""
            continue
        cur += ch
    parts.append(unwrap(cur))
    return [p for p in parts if p]
