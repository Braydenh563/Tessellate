"""The composer as the graph maker (L158, Brief 97, INBOX 1847).

"chart this: Mon 3, Tue 5" (values after a colon or a line break, a Markdown
table, or the answer before) and "chart my notes on running" (the measure the
subject's notes share, one point a note, oldest first) are answered with the
```chart fence the / menu's chart maker saves (`ask-chart.js`,
`drawAskChart.maker`). Chat, Ask and the note view draw that fence with Save
as SVG and CSV, and the answer's Save as a note keeps it as a chart block, so
nothing new is drawn here: this only writes the fence, by plain rule.

The fence is the maker's format: `title:` and `kind:` lines, then `label,
value` a line. A label never carries a comma, semicolon or tab (the maker
splits on them), a value is never negative (the maker skips it), and at most
`MAX_ROWS` rows go in (the maker's own cap).

Notes on the subject with no measure in common are drawn as a Mermaid mind map
instead (`composer_mermaid.from_notes`), and the answer says so. A counted
chart ("chart my notes per month", "show notes per tag") is not read here:
`routes_vision.question_chart` and `composer_talk.chart_ask` draw those.
"""

from __future__ import annotations

import re
from datetime import date

MAX_ROWS = 60
LABEL_CHARS = 60
NAME_CHARS = 24

_QUESTION = re.compile(r"^\W*(?:what|when|where|who|which|why|how|is|are|was|were|does|do|did)\b", re.I)
_SHAPE = r"(?:(?:bar|line|column|pie)\s+)?(?:chart|graph|plot)s?"
_ASK = re.compile(
    r"^\W*(?:(?:please|pls|can you|could you|would you)\s+)?(?:chart|graph|plot|visuali[sz]e)\b"
    rf"|\b(?:make|draw|create|build|generate|give|show|do)\b(?:\s+(?:me|us))?\s+(?:an?|the|some|my)\s+{_SHAPE}\b",
    re.I,
)
#: A chart of counts: the counted charts' words, read elsewhere.
_COUNTED = re.compile(
    r"\b(?:per|by|each|every|a)\s+(?:day|week|month|year|weekday|category|categories|tags?)\b"
    r"|\b(?:daily|weekly|monthly|yearly|over time|how many|number of)\b"
    #: How notes link is the graph view's and the diagrams' (`composer_mermaid`).
    r"|\b(?:links?|linked|linking|connect\w*)\b",
    re.I,
)
_REFERS = re.compile(r"\b(?:this|that|these|those|it|them|the answer|above)\b", re.I)
_LINE = re.compile(r"\b(?:line|trend)\b", re.I)
_PIE = re.compile(r"\bpie\b", re.I)

_UNITS = {
    "km": "km", "kms": "km", "kilometres": "km", "kilometers": "km", "mi": "miles", "mile": "miles", "miles": "miles",
    "kg": "kg", "kgs": "kg", "lb": "lb", "lbs": "lb", "hours": "hours", "hour": "hours", "hrs": "hours", "hr": "hours",
    "h": "hours", "minutes": "minutes", "minute": "minutes", "mins": "minutes", "min": "minutes", "steps": "steps",
    "pages": "pages", "words": "words", "reps": "reps", "kcal": "kcal", "calories": "kcal", "%": "%",
}
_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_UNIT_WORDS = "|".join(sorted((re.escape(u) for u in _UNITS if u != "%"), key=len, reverse=True))
_MEASURE = re.compile(rf"(?<![\w.])(?:(?P<cur>[£$€])\s?(?P<money>{_NUMBER})|(?P<num>{_NUMBER})\s?(?:(?P<unit>{_UNIT_WORDS})\b|(?P<pct>%)))", re.I)
#: A row as typed: a label, a separator, a number (a currency sign before it, a known unit after).
_ROW = re.compile(rf"^(?P<label>.*?)[\s:=,;\t|]*[£$€]?(?P<value>{_NUMBER})\s*(?:%|(?:{_UNIT_WORDS})\b)?[\s.!]*$", re.I)
_PAIR = re.compile(rf"([^\W\d_][^\d,;]*?)\s*[:=]?\s*[£$€]?({_NUMBER})\b\s*")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+(?:\[[ xX]\]\s+)?")

#: What a question's words say the measure is ("my running times" is minutes).
_WANTS = (
    (re.compile(r"\b(?:times?|minutes?|mins?|durations?|long)\b", re.I), ("minutes", "hours")),
    (re.compile(r"\b(?:hours?|sleep|slept)\b", re.I), ("hours", "minutes")),
    (re.compile(r"\b(?:distances?|far|km|kilomet\w*)\b", re.I), ("km", "miles")),
    (re.compile(r"\bmiles?\b", re.I), ("miles", "km")),
    (re.compile(r"\b(?:weights?|weigh\w*|kg|kilos?)\b", re.I), ("kg", "lb")),
    (re.compile(r"\b(?:spend|spent|spending|costs?|money|prices?|paid|bills?)\b", re.I), ("£", "$", "€")),
    (re.compile(r"\bsteps\b", re.I), ("steps",)),
    (re.compile(r"\bpages\b", re.I), ("pages",)),
)
_NOT_SUBJECT = frozenset(
    "chart charts graph graphs plot plots visualise visualize make draw create build generate give show do me us a an the of "
    "my notes note on about for from with this that how please pls can you could would bar line pie column all in i values "
    "numbers data it them what times time minutes mins hours distance distances weight spend spent costs cost money "
    "sleep steps pages km kg miles".split()
)


def asks(question: str) -> bool:
    """Whether the words ask for a chart drawn from values or notes, not a counted one."""
    text = question or ""
    return bool(_ASK.search(text)) and not _QUESTION.search(text) and not _COUNTED.search(text)


# --- values given ---------------------------------------------------------------------


def _number(text: str) -> float:
    value = float(text.replace(",", ""))
    return int(value) if value.is_integer() else value


def _label(text: str) -> str:
    cleaned = " ".join(re.sub(r"[,;\t|]+", " ", text).split()).strip(" -:=*_")
    return cleaned[:LABEL_CHARS].rstrip()


def _row(text: str) -> tuple[str, float] | None:
    line = _BULLET.sub("", text).strip()
    found = _ROW.match(line)
    if not found:
        return None
    raw = found.group("label").rstrip()
    if re.search(r"(?:^|[\s,;:=\t|])-$", raw):
        return None  # "Wed, -2": the maker draws no negative bar
    label = _label(raw)
    return (label, _number(found.group("value"))) if re.search(r"[^\W\d_]", label) else None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(lines: list[str]) -> tuple[list[tuple[str, float]], str]:
    """A Markdown table's rows (the first cell, the first number after it) and its title."""
    rows: list[tuple[str, float]] = []
    header: list[str] = []
    for line in lines:
        cells = _cells(line)
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        at = next((i for i, c in enumerate(cells[1:], 1) if re.fullmatch(rf"[£$€]?(?:{_NUMBER})\s*%?", c)), None)
        if at is None:
            header = header or cells
        elif _label(cells[0]):
            rows.append((_label(cells[0]), _number(re.sub(r"[£$€%\s]", "", cells[at]))))
    title = f"{header[1]} per {header[0].lower()}" if len(header) >= 2 and header[0] and header[1] else ""
    return rows, title[:80]


def table_title(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip().startswith("|")]
    return _table(lines)[1] if lines else ""


def _one_line(line: str) -> list[tuple[str, float]] | None:
    """One line of items: "Mon 3, Tue 5" split on commas, or "Mon 3 Tue 5", a word and a number again and again."""
    items = [_row(part) for part in re.split(r"[,;]\s+", line)]
    if len(items) >= 2 and all(items):
        return [i for i in items if i]
    pairs = _PAIR.findall(line)
    if len(pairs) >= 2 and _PAIR.sub("", line).strip(" ,;.") == "":
        return [(_label(label), _number(value)) for label, value in pairs]
    return None


def rows_of(text: str) -> list[tuple[str, float]]:
    """The (label, value) rows typed or pasted: a table, a line each, or one line of items."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if sum(ln.strip().startswith("|") for ln in lines) >= 2:
        return _table([ln for ln in lines if ln.strip().startswith("|")])[0][:MAX_ROWS]
    items = _one_line(lines[0]) if len(lines) == 1 else None
    return (items or [r for r in (_row(ln) for ln in lines) if r])[:MAX_ROWS]


def _fence(title: str, kind: str, rows: list[tuple[str, float]]) -> str:
    return "\n".join(["```chart", f"title: {title}", f"kind: {kind}", *(f"{label}, {value:g}" if isinstance(value, float) else f"{label}, {value}" for label, value in rows), "```"])


_KEEP = "Save as a note keeps it as a chart block; press it there to change the values or the kind."
HOW = (
    "Give me the values after a colon, a label and a number each (chart this: Mon 3, Tue 5, Wed 4), "
    "or name the notes whose numbers to draw (chart my notes on running). The chart maker is also in a note's / menu."
)


def _given(question: str, previous: str, opened: str) -> str:
    """The text a chart ask means: what follows a colon or a line break, the
    values after "of", else the answer before or the open note for "this"."""
    cut = re.search(r"[:\n]", question)
    if cut and rows_of(question[cut.end():]):
        return question[cut.end():]
    after = re.search(rf"\b{_SHAPE}\s+(?:of|for|from|with)\s+(.+)$", question, re.I | re.S)
    if after and len(rows_of(after.group(1))) >= 2:
        return after.group(1)
    head = question[: cut.start()] if cut else question
    return (previous or opened or "") if _REFERS.search(head) else ""


def _subject_words(question: str) -> list[str]:
    head = re.split(r"[:\n]", question, maxsplit=1)[0]
    return [w for w in re.findall(r"[a-z][a-z0-9']+", head.lower()) if w not in _NOT_SUBJECT and len(w) > 2]


def _chart_answer(rows: list, title: str, question: str) -> dict:
    kind = "line" if _LINE.search(question) else "bar"
    pie = " A pie chart is not drawn here; the bars show the same shares." if _PIE.search(question) else ""
    lead = f"Here are your {len(rows)} values as a {kind} chart.{pie}"
    return {"text": f"{lead}\n\n{_fence(title or 'Chart', kind, rows)}\n\n{_KEEP}", "grounding": [], "answered": True, "shape": "chart", "next": []}


def pasted(question: str, previous: str = "", opened: str = "") -> dict | None:
    """A chart of the values the message gives (or "this", the answer before),
    the two ways to ask when it gives none, or None when it names notes."""
    if not asks(question):
        return None
    given = _given(question, previous, opened)
    rows = rows_of(given)
    if len(rows) >= 2:
        return _chart_answer(rows, table_title(given), question)
    if len(rows) == 1:
        return {"text": "One value is not a chart: give two or more, a label and a number each.", "grounding": [], "answered": True, "next": []}
    if _subject_words(question) and not given:
        return None  # "chart my notes on running": read once the notes are found
    return {"text": HOW, "grounding": [], "answered": True, "next": []}


# --- from the notes ------------------------------------------------------------------


def _measures(text: str) -> dict[str, float]:
    """The first value of each unit in a note's words."""
    found: dict[str, float] = {}
    for got in _MEASURE.finditer(text or ""):
        unit = got.group("cur") or ("%" if got.group("pct") else _UNITS[got.group("unit").lower()])
        found.setdefault(unit, _number(got.group("money") or got.group("num")))
    return found


def _says(note: dict, stems: list[str]) -> bool:
    words = " ".join([str(note.get("title") or ""), str(note.get("content") or ""), " ".join(str(t) for t in note.get("tags") or [])])
    return any(re.search(rf"\b{re.escape(s)}", words, re.I) for s in stems)


def _unit(question: str, measured: list[dict[str, float]]) -> str | None:
    """The unit to draw: the one the question names, else the one most notes carry (two at least)."""
    have: dict[str, int] = {}
    for found in measured:
        for unit in found:
            have[unit] = have.get(unit, 0) + 1
    for pattern, units in _WANTS:
        if pattern.search(question):
            named = next((u for u in units if have.get(u, 0) >= 2), None)
            if named:
                return named
    best = max(have.items(), key=lambda kv: kv[1], default=(None, 0))
    return best[0] if best[1] >= 2 else None


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _mind_map(chosen: list[dict], subject: str) -> dict | None:
    from tessellate.ai import composer_mermaid

    made = composer_mermaid.from_notes(chosen, "mindmap", subject[:1].upper() + subject[1:])
    if made is None:
        return None
    on = f" on {subject}" if subject else ""
    lead = (f"Your note{on} holds" if len(chosen) == 1 else f"Your {len(chosen)} notes{on} hold") + " no numbers with a shared unit to chart, so here they are as a mind map."
    return {"text": f"{lead}\n\n{composer_mermaid.fenced(made)}", "grounding": [], "answered": True, "shape": "diagram", "next": []}


def _labels(points: list[tuple[date | None, dict, float]]) -> list[str]:
    from tessellate.ai import composer_mermaid, composer_write

    names = [_label(composer_write.note_name(n, size=NAME_CHARS)) or "Untitled" for _d, n, _v in points]
    if len(set(names)) == len(names):
        return names
    return [f"{name} {composer_mermaid._day_words(day)}" if day else name for name, (day, _n, _v) in zip(names, points, strict=True)]  # noqa: SLF001


def from_notes(question: str, notes: list[dict]) -> dict | None:
    """"Chart my notes on running": the measure the subject's notes share as a
    chart, one point a note, oldest first; their mind map when they share none;
    None when no note is on the subject."""
    if not asks(question):
        return None
    words = _subject_words(question)
    stems = [w[:5] for w in words]
    chosen = [n for n in notes if (n.get("content") or "").strip() and (not stems or _says(n, stems))][:MAX_ROWS]
    if not chosen:
        return None
    subject = " ".join(words)
    measured = [_measures(str(n.get("content") or "")) for n in chosen]
    unit = _unit(question, measured)
    if unit is None:
        return _mind_map(chosen, subject)
    return _measure_chart(question, chosen, measured, unit, subject)


def _measure_chart(question: str, chosen: list[dict], measured: list[dict[str, float]], unit: str, subject: str) -> dict:
    """The chart of one unit across the notes that name it, oldest first."""
    from tessellate.ai import composer_mermaid

    points = sorted(((composer_mermaid._note_day(n), n, m[unit]) for n, m in zip(chosen, measured, strict=True) if unit in m), key=lambda p: (p[0] or date.max, str(p[1].get("created_at") or ""), p[1].get("id") or 0))  # noqa: SLF001
    rows = list(zip(_labels(points), (v for _d, _n, v in points), strict=True))
    dated = len(rows) >= 3 and all(d for d, _n, _v in points)
    kind = "line" if dated and not re.search(r"\bbar\b", question, re.I) else "bar"
    title = f"{subject[:1].upper() + subject[1:]}: {unit} per note" if subject else f"{unit[:1].upper() + unit[1:]} per note"
    on = f" on {subject}" if subject else ""
    left = len(chosen) - len(rows)
    other = f" {left} other {_plural(left, 'note', 'notes')} on it {_plural(left, 'names', 'name')} no {unit}." if left else ""
    lead = f"Your {len(rows)} notes{on}, charted by {unit}, oldest first.{other}"
    return {"text": f"{lead}\n\n{_fence(title[:80], kind, rows)}\n\n{_KEEP}", "grounding": [], "answered": True, "shape": "chart", "next": []}
