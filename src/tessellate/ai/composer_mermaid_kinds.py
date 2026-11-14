"""Gantt, pie, state, class and ER diagrams by plain rule (L-documents-101).

`composer_mermaid` drew a flowchart, a timeline or a mind map; a person in the builder's pie chart who pressed
Describe it got a flowchart of their words. Each kind here reads the shape its words have and writes the source the
builder's own printer writes (`diagram-kinds-more.js`), so what is drawn opens as blocks and prints back unchanged:

- **gantt**: steps (a list or "then" clauses) as tasks one after another, "(3 days)" or "(2 weeks)" their length;
- **pie**: lines that end in a number ("Rent: 1200", "Fun - 150", "40% Food"), at least two;
- **state**: steps as states in order, from the start mark to the end mark;
- **class**, **er**: each heading with its bullets as a class with members, or an entity with attributes; "A has many B"
  between two of them is a relationship.

Each function returns the Mermaid source or None when the words do not have the shape (the caller then falls back
and says so). Ids are generated or cut to letters and digits, and every label drops the characters its line uses as
separators, so a model-free reply cannot write a line the parser reads differently.
"""

from __future__ import annotations

import re
from datetime import date

MAX_ROWS = 16
_DURATION = re.compile(r"\(?\b(\d{1,3})\s*(day|days|d|week|weeks|w)\b\)?", re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NUMBER_LAST = re.compile(r"^(.*?\S)\s*(?:[:=\-–]|\s)\s*(\d+(?:\.\d+)?)\s*%?$")
_NUMBER_FIRST = re.compile(r"^(\d+(?:\.\d+)?)\s*%?\s+(?:of\s+|for\s+)?(\S.*)$")
_RELATES = re.compile(r"^(\w[\w ]*?)\s+(has many|has one|has|belongs to|owns|contains)\s+(\w[\w ]*)$", re.I)
_MEMBER = re.compile(r"^(.*?\S)\s*:\s*(.*\S)$")


def _plain(text: str, limit: int = 40) -> str:
    """Words for a label: spaces folded, the characters a line uses as separators dropped."""
    text = " ".join(re.sub(r"[\"'`:;,#{}\[\]()<>|\\]", " ", text or "").split())
    return text[:limit].strip()


def _ident(text: str) -> str:
    """CamelCase letters and digits, never starting with a digit."""
    word = "".join(part[:1].upper() + part[1:] for part in re.findall(r"[A-Za-z0-9]+", text or ""))
    return word if word and not word[0].isdigit() else ("N" + word if word else "")


def _title(rows: list[tuple[str, int, bool, str]]) -> str:
    """The first heading, else a short first line that stands above the list ("Launch plan")."""
    head = next((_plain(w, 60) for k, _d, _n, w in rows if k == "heading"), "")
    first = rows[0] if rows else None
    if not head and first and first[0] == "line" and len(first[3]) <= 60 and len(rows) > 1 and not first[3].endswith((".", "?", "!")):
        head = _plain(first[3], 60)
    return head


def _items(text: str, lines) -> list[str]:  # noqa: ANN001
    from tessellate.ai import composer_mermaid as cm

    return cm.steps(text) or [w for k, d, _n, w in lines if k == "item" and d == 1]


def gantt(text: str, today: date) -> str | None:
    from tessellate.ai import composer_mermaid as cm

    lines = cm._lines(text)
    items = _items(text, lines)
    if len(items) < 2:
        return None
    iso = _ISO.search(text or "")
    try:
        start = date(*map(int, iso.groups())) if iso else today
    except ValueError:
        start = today
    out = ["gantt", "    dateFormat YYYY-MM-DD"]
    if _title(lines):
        out.insert(1, f"    title {_title(lines)}")
    for n, item in enumerate(items[:MAX_ROWS], 1):
        span = _DURATION.search(item)
        days = (int(span.group(1)) * (7 if span.group(2).lower().startswith("w") else 1)) if span else 1
        name = _plain(_DURATION.sub("", item)) or f"Task {n}"
        when = start.isoformat() if n == 1 else f"after t{n - 1}"
        out.append(f"    {name} :t{n}, {when}, {max(1, days)}d")
    return "\n".join(out) + "\n"


def pie(text: str) -> str | None:
    from tessellate.ai import composer_mermaid as cm

    lines = cm._lines(text)
    slices = []
    for kind, _d, _n, words in lines:
        if kind == "heading":
            continue
        words = re.sub(r"^\s*[-*+]\s+", "", words).strip()
        hit = _NUMBER_LAST.match(words)
        if hit:
            name, value = hit.group(1), hit.group(2)
        elif (hit := _NUMBER_FIRST.match(words)):
            name, value = hit.group(2), hit.group(1)
        else:
            continue
        name = _plain(name, 30)
        if name and float(value) > 0:
            slices.append((name, value))
    if len(slices) < 2:
        return None
    head = f"pie title {_title(lines)}" if _title(lines) else "pie"
    return "\n".join([head, *(f'    "{name}" : {value}' for name, value in slices[:MAX_ROWS])]) + "\n"


def state(text: str) -> str | None:
    from tessellate.ai import composer_mermaid as cm

    items = _items(text, cm._lines(text))
    if len(items) < 2:
        return None
    names = [_plain(i) or f"State {n}" for n, i in enumerate(items[:MAX_ROWS], 1)]
    out = ["stateDiagram-v2", *(f'    state "{name}" as s{n}' for n, name in enumerate(names, 1)), "    [*] --> s1"]
    out += [f"    s{n} --> s{n + 1}" for n in range(1, len(names))]
    out.append(f"    s{len(names)} --> [*]")
    return "\n".join(out) + "\n"


def _sections(text: str) -> tuple[list[tuple[str, list[str]]], list[tuple[str, str, str]]]:
    """([(name, members)], [(from, verb, to)]): a heading with its bullets, or "Name: a, b" lines; and "A has many B"."""
    from tessellate.ai import composer_mermaid as cm

    found: list[tuple[str, list[str]]] = []
    links: list[tuple[str, str, str]] = []
    for kind, _d, _n, words in cm._lines(text):
        if kind == "heading":
            found.append((words, []))
        elif kind == "item" and found:
            found[-1][1].append(words)
        elif kind == "line":
            link = _RELATES.match(words.strip(" ."))
            member = _MEMBER.match(words)
            if link:
                links.append((link.group(1), link.group(2).lower(), link.group(3)))
            elif member:
                found.append((member.group(1), [m.strip() for m in re.split(r"[,;]", member.group(2)) if m.strip()]))
    return found[:MAX_ROWS], links


def _linked(names: dict[str, str], links: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    def known(word: str) -> str | None:
        key = re.sub(r"s$", "", word.strip().lower())
        return next((v for k, v in names.items() if re.sub(r"s$", "", k) == key), None)

    return [(a, verb, b) for a, verb, b in ((known(x), v, known(z)) for x, v, z in links) if a and b and a != b]


def _member(words: str) -> str:
    """A class member: "id: int" keeps its type after a colon, anything else is its plain words."""
    typed = _MEMBER.match(words)
    return f"{_plain(typed.group(1), 30)}: {_plain(typed.group(2), 20)}" if typed and _plain(typed.group(1), 30) and _plain(typed.group(2), 20) else _plain(words, 40)


def klass(text: str) -> str | None:
    found, links = _sections(text)
    named = [(_ident(name), members) for name, members in found if _ident(name)]
    if len(named) < 2 and not (named and named[0][1]):
        return None
    out = ["classDiagram"]
    for name, members in named:
        out.append(f"    class {name} {{" if members else f"    class {name}")
        out += [f"        +{_member(m)}" for m in members if _member(m)]
        if members:
            out.append("    }")
    ids = {name.lower(): name for name, _m in named}
    out += [f"    {a} --> {b} : {verb}" for a, verb, b in _linked(ids, links)]
    return "\n".join(out) + "\n"


def _type_of(attribute: str) -> tuple[str, str]:
    """(type, name) of "placed date", "id: int", "email": the type the words give, else a guess from the name."""
    words = _plain(attribute, 40)
    hit = re.match(r"^(\w+)\s+(int|integer|string|text|float|date|datetime|boolean|bool)$", words, re.I)
    if hit:
        return _norm(hit.group(2)), _ident(hit.group(1)).lower()
    typed = _MEMBER.match(attribute)
    if typed and re.fullmatch(r"\w+", typed.group(2).strip()):
        return _norm(typed.group(2).strip()), _ident(typed.group(1)).lower()
    name = _ident(words).lower()
    return ("int" if name == "id" or name.endswith("id") or name in ("count", "number", "quantity") else "string"), name


def _norm(word: str) -> str:
    return {"integer": "int", "bool": "boolean", "text": "string"}.get(word.lower(), word.lower())


def er(text: str) -> str | None:
    found, links = _sections(text)
    named = [(_ident(name).upper(), members) for name, members in found if _ident(name)]
    if len(named) < 2 and not (named and named[0][1]):
        return None
    out = ["erDiagram"]
    for name, members in named:
        if not members:
            out.append(f"    {name}")
            continue
        out.append(f"    {name} {{")
        rows = [_type_of(m) for m in members]
        out += [f"        {kind} {attr}" for kind, attr in rows if attr]
        out.append("    }")
    ids = {name.lower(): name for name, _m in named}
    for a, verb, b in _linked(ids, links):
        many = verb in ("has many", "owns", "contains")
        out.append(f"    {a} ||--{'o{' if many else 'o|'} {b} : {'has' if verb.startswith('has') else verb.replace(' ', '_')}")
    return "\n".join(out) + "\n"
