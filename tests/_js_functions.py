"""Function bodies of a classic-script JS file, for lints that ask "which function does this line run in".

`blank` turns comments, strings, template text and regex literals into spaces
(newlines kept, so offsets and line numbers hold), which leaves only code
braces; `function_spans` pairs them and keeps the ones that open a function
body: an arrow's, a `function`'s, a method's. A heuristic, not a parser, with
one rule for a `/`: after an operator, an opening bracket or `return`, it
starts a regex literal.
"""

from __future__ import annotations

import re

_NORMAL = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`|/|\$\{|[{}]", re.S)
_TEMPLATE = re.compile(r"\\.|`|\$\{", re.S)
_REGEX = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[a-z]*")
_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WORDS = ("return", "typeof", "case", "void", "await", "yield", "in", "of")
_NOT_FUNCTION = {"if", "for", "while", "switch", "catch", "with"}


def _regex_may_start(text: str, at: int) -> bool:
    k = at - 1
    while k >= 0 and text[k] in " \t\r\n":
        k -= 1
    if k < 0 or text[k] in _REGEX_AFTER:
        return True
    return any(text[max(0, k - len(w) + 1) : k + 1] == w for w in _REGEX_WORDS)


def blank(text: str) -> str:
    wipe: list[tuple[int, int]] = []
    stack: list[int] = []  # brace depth of each open `${`; empty means top-level code
    i, n = 0, len(text)
    in_template = False
    while i < n:
        if in_template:
            m = _TEMPLATE.search(text, i)
            if not m:
                wipe.append((i, n))
                break
            if m.group() == "`":
                wipe.append((i, m.end()))
                in_template, i = False, m.end()
            elif m.group() == "${":
                wipe.append((i, m.end()))
                stack.append(0)
                in_template, i = False, m.end()
            else:
                i = m.end()
            continue
        m = _NORMAL.search(text, i)
        if not m:
            break
        token, start = m.group(), m.start()
        if token == "`":
            wipe.append((start, m.end()))
            in_template, i = True, m.end()
            continue
        if token == "/":
            if _regex_may_start(text, start):
                r = _REGEX.match(text, start)
                if r:
                    wipe.append((start, r.end()))
                    i = r.end()
                    continue
            i = m.end()
            continue
        if token == "{" and stack:
            stack[-1] += 1
        elif token == "}" and stack:
            if stack[-1] == 0:
                stack.pop()
                wipe.append((start, m.end()))
                in_template, i = True, m.end()
                continue
            stack[-1] -= 1
        if token not in "{}" and token != "${":
            wipe.append((start, m.end()))
        i = m.end()
    out, at = [], 0
    for a, b in wipe:
        out.append(text[at:a])
        out.append(re.sub(r"[^\n]", " ", text[a:b]))
        at = b
    out.append(text[at:])
    return "".join(out)


def _name(code: str, brace: int) -> str | None:
    j = brace - 1
    while j >= 0 and code[j].isspace():
        j -= 1
    if code[j - 1 : j + 1] == "=>":
        m = re.search(r"(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^()]*\)|[\w$]+)\s*=>\s*$", code[max(0, j - 300) : j + 1])
        return m.group(1) if m else "arrow"
    if code[j] != ")":
        return None
    level, k = 0, j
    while k >= 0:
        level += {")": 1, "(": -1}.get(code[k], 0)
        if level == 0:
            break
        k -= 1
    m = re.search(r"([\w$]+)\s*$", code[max(0, k - 80) : k])
    return m.group(1) if m and m.group(1) not in _NOT_FUNCTION else None


def function_spans(text: str) -> list[tuple[int, int, str]]:
    """(open brace, close brace, name) for every function body; an unnamed arrow is "arrow"."""
    code = blank(text)
    spans, stack = [], []
    for m in re.finditer(r"[{}]", code):
        if m.group() == "{":
            stack.append(m.start())
        elif stack:
            start = stack.pop()
            name = _name(code, start)
            if name is not None:
                spans.append((start, m.start(), name))
    return spans
