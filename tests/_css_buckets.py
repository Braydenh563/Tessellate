"""Which style rules land in Blink's universal rule bucket.

Blink files every rule under one simple selector of its rightmost compound
(an id, a class, an attribute name or a tag) and tries it only on elements
that carry it. A rule whose rightmost compound has none of these is tried on
every element at every style recalc: at 4x CPU, 633 such rules cost about
1.7 ms of a key's 5.1 ms of style in the 20,000 word document (L342). A
single-argument `:is()` or `:where()` is looked into and bucketed by what it
holds; one with two or more arguments is not, so `X :is(.a, .b)` is tried
everywhere while `X :is(.a), X :is(.b)` is tried only on `.a` and `.b`
(measured with the selector-stats trace on Chromium 1243).

Not named `test_*.py`: pytest would collect it and find no tests.
"""

from __future__ import annotations

import re

_IDENT = re.compile(r"-?[_a-zA-Z -￿][-_a-zA-Z0-9 -￿]*|\\.")


def split_top(text: str, seps: str = ",") -> list[str]:
    """Split on any of `seps` outside brackets, parens and strings."""
    out, depth, cur, quote, i = [], 0, [], "", 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif ch in seps and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


def _close(text: str, i: int) -> int:
    """Index just past the bracket or paren that opens at text[i]."""
    pair = {"(": ")", "[": "]"}[text[i]]
    depth, quote, j = 0, "", i
    while j < len(text):
        ch = text[j]
        if quote:
            if ch == "\\":
                j += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
            if depth == 0:
                assert ch == pair
                return j + 1
        j += 1
    raise ValueError(f"unbalanced selector: {text!r}")


def rightmost(sel: str) -> tuple[str, str]:
    """(prefix, rightmost compound) of a complex selector."""
    sel = sel.strip()
    depth, quote, cut, j = 0, "", 0, 0
    while j < len(sel):
        ch = sel[j]
        if quote:
            if ch == "\\":
                j += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and ch in " \t\n>+~":
            cut = j + 1
        elif depth == 0 and ch == "\\":
            j += 1
        j += 1
    return sel[:cut], sel[cut:]


def simples(compound: str) -> list[str]:
    """The simple selectors of one compound, in order."""
    out, i = [], 0
    while i < len(compound):
        ch = compound[i]
        if ch == "[":
            j = _close(compound, i)
        elif ch in ".#":
            m = _IDENT.match(compound, i + 1)
            j = i + 1
            while m and m.start() == j:
                j = m.end()
                m = _IDENT.match(compound, j)
        elif ch == ":":
            j = i + (2 if compound.startswith("::", i) else 1)
            m = _IDENT.match(compound, j)
            j = m.end() if m else j
            if j < len(compound) and compound[j] == "(":
                j = _close(compound, j)
        elif ch in "*&|":
            j = i + 1
        else:
            m = _IDENT.match(compound, i)
            if not m:
                raise ValueError(f"cannot read {compound!r} at {i}")
            j = m.end()
        out.append(compound[i:j])
        i = j
    return out


def _arg(simple: str) -> str:
    return simple[simple.index("(") + 1 : -1]


#: Pseudo-classes with a bucket of their own (selector stats: 0 attempts on
#: 1,000 plain divs, against 1,000 for `:hover` or `:first-child`).
_OWN_BUCKET = (":focus", ":focus-visible", ":link", ":any-link", ":root")
#: Every element with a class is in the `class` attribute's bucket, so a rule
#: filed there is tried on most of the page (670 of 917 elements measured).
_WIDE_ATTR = re.compile(r"\[\s*(class|style)\b", re.I)


def bucketed(sel: str) -> bool:
    """Whether Blink files this complex selector under an id, class, attribute or tag."""
    _, comp = rightmost(sel)
    for s in simples(comp):
        low = s.lower()
        if s[0] in ".#" or _IDENT.fullmatch(s) or low in _OWN_BUCKET:
            return True
        if s[0] == "[" and not _WIDE_ATTR.match(s):
            return True
        if low.startswith((":is(", ":where(")):
            args = split_top(_arg(s))
            if len(args) == 1 and bucketed(args[0]):
                return True
    return False


def split_candidate(sel: str):
    """For an unbucketed selector whose rightmost compound holds a list
    `:is()` or `:where()` of bucketable arguments: (prefix, before, the
    pseudo's name, its arguments, after). None otherwise."""
    if bucketed(sel):
        return None
    pre, comp = rightmost(sel)
    parts = simples(comp)
    for k, s in enumerate(parts):
        low = s.lower()
        if low.startswith((":is(", ":where(")):
            args = [a.strip() for a in split_top(_arg(s))]
            if len(args) > 1 and all(a and bucketed(a) for a in args):
                return pre, "".join(parts[:k]), low[1 : low.index("(")], args, "".join(parts[k + 1 :])
    return None


def style_preludes(css: str):
    """(start, end, parent) of every style rule's selector text, skipping
    comments, strings, at-rule preludes and keyframe selectors; parent is
    the index in the result of the style rule it is nested in, or None."""
    out, i, seg, stack, n = [], 0, 0, [], len(css)
    owners: list = []
    while i < n:
        ch = css[i]
        if css.startswith("/*", i):
            i = css.index("*/", i + 2) + 2
            continue
        if ch in "\"'":
            j = i + 1
            while css[j] != ch:
                j += 2 if css[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "(":
            depth = 1
            i += 1
            while depth:
                depth += {"(": 1, ")": -1}.get(css[i], 0)
                i += 1
            continue
        if ch == "{":
            while "*/" in css[seg:i]:
                seg = css.index("*/", seg) + 2
            text = css[seg:i]
            head = text.strip()
            kind = "at" if head.startswith("@") else "rule"
            if re.match(r"@(-[a-z]+-)?keyframes", head.lower()):
                kind = "keyframes"
            elif stack and stack[-1] == "keyframes":
                kind = "frame"
            parent = next((o for o in reversed(owners) if o is not None), None)
            if kind == "rule":
                lead = len(text) - len(text.lstrip())
                out.append((seg + lead, seg + lead + len(head), parent))
                owners.append(len(out) - 1)
            else:
                owners.append(None)
            stack.append(kind)
            seg = i + 1
        elif ch == "}":
            stack.pop()
            owners.pop()
            seg = i + 1
        elif ch == ";":
            seg = i + 1
        i += 1
    return out


def universal_selectors(css: str) -> list[str]:
    """Every selector (one item of a rule's list) left in the universal bucket."""
    out = []
    for a, b, _ in style_preludes(css):
        for sel in split_top(css[a:b]):
            if sel.strip() and not bucketed(sel):
                out.append(sel.strip())
    return out
