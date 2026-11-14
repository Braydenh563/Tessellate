"""A Mermaid diagram from text or notes, by plain rule (INBOX 1466).

The owner, 2026-10-31: "can it be used to generate mermaid diagrams??". The
app already draws every ```mermaid fence (mermaid-draw.js, in notes, chat,
Ask and documents); this writes the fence, from the shape the words have:

- **steps** (a numbered list, a checklist, or lines that go "first ... then
  ... finally") are a `flowchart TD`, one box a step, an arrow between each;
- **dated lines** ("2 April: tomatoes in"), or notes with the day each was
  written, are a `timeline`, oldest first;
- **a heading with bullets** (nested or not), or a subject with its notes,
  is a `mindmap`, the heading or subject at the root.

Asked for one by name ("make a flowchart"), that one is drawn when the words
have its shape; otherwise the shape they have is drawn and `note` says why.

**Safe by construction.** Ids are `n1`, `n2`...; a box's words are quoted,
with `"`, `#`, `<` and `>` written as Mermaid's entity codes and a backtick
as a quote mark; a timeline's words drop its separators (`:`, `;`, `#`).
At most `MAX_NODES` boxes: past that the last says how many more there are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MAX_NODES = 16
#: A note's name in a box: the composer's own naming, cut shorter.
NAME_CHARS = 40
LABEL_CHARS = 60
#: A mind map's branch shows at most this many points under it.
BRANCH_POINTS = 3

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
#: A date as written: 2026-04-02, 2/4/2026, 2 April (2026), April 2(nd)(, 2026), April 2026, 2026.
_DATE = re.compile(
    rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\.?(?:,?\s+\d{{4}})?"
    rf"|{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|{_MONTH}\.?\s+\d{{4}}|(?:19|20)\d{{2}})\b",
    re.I,
)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
_ITEM = re.compile(r"^(\s*)(?:([-*+])|(\d{1,3})[.)])\s+(?:\[[ xX]\]\s+)?(.*\S)\s*$")
#: A checklist line: a bullet, then a `[ ]` or `[x]` box (1546 P3: a note of tasks is a flow).
_TASK = re.compile(r"^(\s*)[-*+]\s+\[[ xX]\]\s+(.*\S)\s*$")
_STEP_WORD = re.compile(r"^(?:first(?:ly)?|then|next|after that|afterwards|finally|lastly|step \d+)\b[,:]?\s*", re.I)
_THEN = re.compile(r"(?:[,;.]\s*|\s+)(?:and\s+)?(?:then|after that|afterwards|next|finally)\b[,:]?\s+", re.I)


@dataclass
class Diagram:
    shape: str  # "flowchart" | "timeline" | "mindmap"
    source: str  # the Mermaid code, without the fence
    nodes: int
    note: str = ""


# --- what was asked for ------------------------------------------------------------

_WANT = (
    ("flowchart", re.compile(r"\b(?:flow\s?-?charts?|flow diagrams?|process (?:map|diagram)|steps? diagram)\b", re.I)),
    ("timeline", re.compile(r"\btime\s?-?lines?\b", re.I)),
    ("mindmap", re.compile(r"\b(?:mind\s?-?maps?|concept maps?|spider diagrams?)\b", re.I)),
    ("", re.compile(r"\b(?:diagrams?|charts?|graphs?|mermaid|visual(?:i[sz]e)?)\b", re.I)),
)
#: A diagram is asked for by a drawing verb aimed at a diagram noun, with a
#: subject ("of", "for", "from"...) or an object ("this", "my notes") and "as"
#: or "into": "make a flowchart of the move", "turn this into a mind map". A
#: question that only mentions a diagram ("the project timeline", "notes on
#: heart diagrams", "show me my mind map") is an ordinary question.
_SHAPE = r"(?:flow\s?-?charts?|flow diagrams?|time\s?-?lines?|mind\s?-?maps?|concept maps?|diagrams?|charts?|mermaid)"
_ASK_MAKE = re.compile(
    r"\b(?:make|draw|sketch|create|build|generate|render|plot|map(?: out)?)\b[^.?!:\n]{0,30}?"
    rf"\b(?:an?|the|my|some|one)\s+(?:[a-z]+\s+){{0,2}}?{_SHAPE}"
    r"(?:\s+(?:of|for|from|about|on|showing|that|which|using)\s+\S|\s*[:\n]\s*\S)",
    re.I,
)
_ASK_TURN = re.compile(
    r"\b(?:turn|convert|put|make|show|draw|map|sketch|render)\b\s+(?:me\s+|us\s+)?\S+(?:\s+\S+){0,7}?\s+(?:as|into|to)\s+"
    rf"(?:an?\s+)?(?:[a-z]+\s+)?{_SHAPE}\b",
    re.I,
)
#: A question about diagrams, not a request for one.
_QUESTION = re.compile(r"^\W*(?:what|when|where|who|whom|whose|which|why|how|do|does|did|is|are|was|were|has|have|had|am)\b", re.I)


def wanted(text: str) -> str:
    """The shape a phrase names ("flowchart", "timeline", "mindmap"), "" for
    any diagram, None when it names none."""
    for shape, pattern in _WANT:
        if pattern.search(text or ""):
            return shape
    return ""


def asks(question: str) -> bool:
    """Whether a chat question asks for a diagram ("make a flowchart of ...")."""
    text = question or ""
    if _QUESTION.search(text):
        return False
    return bool(_ASK_MAKE.search(text) or _ASK_TURN.search(text))


# --- labels and ids -----------------------------------------------------------------


def _words(text: str) -> str:
    """Plain words: markdown off, links to their text, spaces folded, cut."""
    text = re.sub(r"\[\[([^\]|]{1,200})(?:\|([^\]]{1,200}))?\]\]", lambda m: m.group(2) or m.group(1), text or "")
    text = re.sub(r"\[([^\]]{1,200})\]\([^)]{0,500}\)", r"\1", text)
    text = re.sub(r"(\*\*|__|~~|`)", "", text)
    text = " ".join(text.split()).strip(" -:;,")
    if len(text) > LABEL_CHARS:
        text = text[: LABEL_CHARS - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return text


def label(text: str) -> str:
    """Words for inside a quoted Mermaid box: `"..."` with entities."""
    text = _words(text).replace("#", "#35;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")
    return f'"{text}"'


def mind_label(text: str) -> str:
    """Words for a mind map box: quoted, with no entity codes (a mind map draws `#35;` as written).

    A quote becomes an apostrophe, and a `#` that would read as the start of a code is left out."""
    text = re.sub(r"#(?=\w+;)", "", _words(text).replace('"', "'"))
    return f'"{text}"'


def _event(text: str) -> str:
    """Words for a timeline line, whose separators are `:` (and `;`, `#`)."""
    return _words(text).replace(":", " -").replace(";", ",").replace("#", "").replace('"', "'").strip() or "…"


# --- reading the text ---------------------------------------------------------------


def _lines(text: str) -> list[tuple[str, int, bool, str]]:
    """(kind, depth, numbered, words) per line: "heading", "item", "line"."""
    out = []
    indents: list[int] = []  # the open list levels' indents, outermost first
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        if not raw.strip() or raw.strip().startswith("```"):
            continue
        heading = _HEADING.match(raw)
        item = _ITEM.match(raw)
        if item:
            indent = len(item.group(1).expandtabs(4))
            while indents and indents[-1] > indent:
                indents.pop()
            if not indents or indents[-1] < indent:
                indents.append(indent)
            out.append(("item", len(indents), bool(item.group(3)), item.group(4)))
            continue
        indents = []
        #: A heading's depth is its level (1 to 6), which `tree` nests by.
        out.append(("heading", len(raw.strip()) - len(raw.strip().lstrip("#")), False, heading.group(1)) if heading else ("line", 0, False, raw.strip()))
    return out


def _sentences(text: str) -> list[str]:
    from tessellate.ai import composer_write

    return [s for kind, _d, _n, words in _lines(text) if kind == "line" for s in composer_write.sentences(words)]


def _listed_steps(lines: list) -> list[str]:
    """A list's top items when they are steps: numbered, or most of them
    opening "first", "then", "finally"."""
    numbered = [words for kind, depth, num, words in lines if kind == "item" and num and depth == 1]
    if len(numbered) >= 2:
        return numbered
    items = [words for kind, depth, _n, words in lines if kind == "item" and depth == 1]
    if len(items) >= 3 and sum(1 for i in items if _STEP_WORD.match(i)) >= 2:
        return [_STEP_WORD.sub("", i) for i in items]
    return []


def _checklist(text: str) -> list[str]:
    """The top-level items of a checklist, in order, when there are at least
    two: tasks are done one after another, so they read as steps."""
    rows = [m for m in (_TASK.match(raw) for raw in (text or "").replace("\r\n", "\n").split("\n")) if m]
    if not rows:
        return []
    top = min(len(m.group(1).expandtabs(4)) for m in rows)
    found = [m.group(2) for m in rows if len(m.group(1).expandtabs(4)) == top]
    return found if len(found) >= 2 else []


def steps(text: str) -> list[str]:
    """The steps the text gives, in order: a numbered list's items, a
    checklist's, else sentences or clauses joined by "then", when there are at
    least three."""
    listed = _listed_steps(_lines(text)) or _checklist(text)
    if listed:
        return listed
    clauses = [c for s in _sentences(text) for c in _THEN.split(s) if c.strip()]
    marked = sum(1 for s in _sentences(text) if _THEN.search(s) or _STEP_WORD.match(s))
    if len(clauses) >= 3 and marked >= 1:
        return [_STEP_WORD.sub("", c).strip(" .") for c in clauses if c.strip(" .")]
    return []


def _sort_key(found: str, index: int) -> tuple:
    """A date as written, as (year, month, day) for ordering; unknown parts
    sort first, and the line's own place breaks ties."""
    iso = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", found)
    if iso:
        return (int(iso.group(1)), int(iso.group(2)), int(iso.group(3)), index)
    low = found.lower()
    month = next((i + 1 for i, m in enumerate(_MONTHS) if re.search(rf"\b{m}", low)), 0)
    year = re.search(r"\b(\d{4})\b", found)
    day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", re.sub(r"\b\d{4}\b", "", found))
    return (int(year.group(1)) if year else 0, month, int(day.group(1)) if day and month else 0, index)


def dated(text: str) -> list[tuple[str, str]]:
    """(date as written, what happened) for every line or sentence with a
    date, oldest first."""
    found = []
    pieces = [w for kind, _d, _n, w in _lines(text) if kind == "item"] + _sentences(text)
    for index, piece in enumerate(pieces):
        match = _DATE.search(piece)
        if not match:
            continue
        rest = (piece[: match.start()] + piece[match.end():]).strip()
        rest = re.sub(r"^(?:on|in|by|from|at)\s+", "", rest.strip(" ,:;-.\u2013"), flags=re.I)
        found.append((_sort_key(match.group(0), index), match.group(0), rest or piece))
    found.sort(key=lambda row: row[0])
    return [(when, what) for _key, when, what in found]


def _outline_branches(lines: list, base: int) -> list[tuple[int, str]]:
    """Each sub-heading nests by its level; the points below it sit one step under."""
    branches: list[tuple[int, str]] = []
    under = 0  # the depth of the sub-heading the points below belong to
    first = next(at for at, row in enumerate(lines) if row[0] == "heading")
    for at, (kind, depth, _n, words) in enumerate(lines):
        if at == first:
            continue
        if kind == "heading":
            under = max(1, depth - base)
            branches.append((under, words))
        elif kind == "item":
            branches.append((under + depth, words))
    return branches


def tree(text: str) -> tuple[str, list[tuple[int, str]]]:
    """(root, [(depth, words)]) of a heading with bullets, or of the first
    sentence with the rest as branches. A document with several sections
    (two or more sub-headings that carry points) is an outline: each
    sub-heading nests by its level and its points sit under it."""
    lines = _lines(text)
    root = next((w for kind, _d, _n, w in lines if kind == "heading"), "")
    heads = [row for row in lines if row[0] == "heading"]
    if _outline(lines):
        branches = _outline_branches(lines, heads[0][1])
    else:
        branches = [(depth, words) for kind, depth, _n, words in lines if kind == "item"]
        branches += [(1, words) for kind, _d, _n, words in lines if kind == "heading" and words != root]
    return _rooted(text, root, branches)


def _rooted(text: str, root: str, branches: list[tuple[int, str]]) -> tuple[str, list[tuple[int, str]]]:
    """The sentences as branches when nothing else gave any, and a root from the text when it has none."""
    if not branches:
        said = _sentences(text)
        if not root and said:
            root, said = said[0], said[1:]
        branches = [(1, s) for s in said]
    if not root:
        from tessellate.ai import no_model_text

        root = no_model_text.draft_title(text) or "Notes"
    return root, branches


def _outline(lines: list) -> bool:
    """Whether the lines are sections: after the first heading, two or more
    sub-headings each followed by at least one point, or headings alone (a
    document's outline, nothing under them)."""
    heads = [i for i, row in enumerate(lines) if row[0] == "heading"]
    if len(heads) < 2:
        return False
    rest = lines[heads[0] + 1 :]
    if not any(row[0] == "item" for row in rest):
        return True
    carrying = 0
    for i, row in enumerate(rest):
        if row[0] == "heading" and i + 1 < len(rest) and rest[i + 1][0] == "item":
            carrying += 1
    return carrying >= 2


# --- writing the diagram ----------------------------------------------------------------


def _capped(rows: list, room: int = MAX_NODES) -> tuple[list, int]:
    return (rows, 0) if len(rows) <= room else (rows[: room - 1], len(rows) - (room - 1))


def flowchart(items: list[str]) -> Diagram:
    shown, more = _capped(items)
    labels = [label(i[:1].upper() + i[1:]) for i in shown] + ([label(f"and {more} more steps")] if more else [])
    lines = ["flowchart TD"] + [f"  n{i + 1}[{text}]" for i, text in enumerate(labels)]
    lines += [f"  n{i + 1} --> n{i + 2}" for i in range(len(labels) - 1)]
    return Diagram("flowchart", "\n".join(lines), len(labels))


def timeline(rows: list[tuple[str, str]], title: str = "") -> Diagram:
    """One line a date; events on the same date share it."""
    merged: list[tuple[str, list[str]]] = []
    for when, what in rows:
        if merged and merged[-1][0].lower() == when.lower():
            merged[-1][1].append(what)
        else:
            merged.append((when, [what]))
    shown, more = _capped(merged)
    lines = ["timeline"] + ([f"  title {_event(title)}"] if title else [])
    lines += [f"  {_event(when)} : " + " : ".join(_event(w) for w in whats) for when, whats in shown]
    if more:
        lines.append(f"  Later : and {more} more")
    return Diagram("timeline", "\n".join(lines), len(shown) + (1 if more else 0))


def mindmap(root: str, branches: list[tuple[int, str]]) -> Diagram:
    """The root as a circle, each branch indented under its parent."""
    shown, more = _capped(branches, MAX_NODES - 1)
    top = min((d for d, _w in shown), default=1)
    lines = ["mindmap", f"  root(({mind_label(root)}))"]
    for i, (depth, words) in enumerate(shown):
        lines.append("  " * (depth - top + 2) + f"n{i + 1}[{mind_label(words)}]")
    if more:
        lines.append(f"    n{len(shown) + 1}[{mind_label(f'and {more} more')}]")
    return Diagram("mindmap", "\n".join(lines), 1 + len(shown) + (1 if more else 0))


def fenced(made: Diagram) -> str:
    return f"```mermaid\n{made.source}\n```"


#: What a diagram's first line may open with: the kinds Mermaid draws that the
#: app's frame accepts. Anything else is not a diagram.
_HEADERS = re.compile(
    r"^(?:flowchart|graph|mindmap|timeline|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|gitGraph|quadrantChart|requirementDiagram|sankey(?:-beta)?|xychart(?:-beta)?|block(?:-beta)?|kanban)\b"
)
MAX_SOURCE = 20000


def _skip_blank(text: str, at: int) -> int:
    while at < len(text) and text[at] in " \t":
        at += 1
    return at


def _fence_body(text: str) -> str | None:
    """The body of the first ```` ``` ```` or ```` ```mermaid ```` fence that closes, or None.
    A scan, not a regex: a lazy body before a closing fence with blanks either side
    is polynomial on a reply of fences and tabs (CodeQL 1996), and the reply is the
    model's, so its shape is not ours to trust."""
    start = text.find("```")
    while start >= 0:
        at = _skip_blank(text, start + 3)
        if text.startswith("mermaid", at):
            at = _skip_blank(text, at + 7)
        if at < len(text) and text[at] == "\n":
            line = text.find("\n", at + 1)
            while line >= 0:
                if text.startswith("```", _skip_blank(text, line + 1)):
                    return text[at + 1 : line]
                line = text.find("\n", line + 1)
            return None
        start = text.find("```", start + 3)
    return None


def source_of(reply: str) -> tuple[str, str]:
    """(the Mermaid source in a model's reply, "") or ("", why it is not one)
    (1546 P3, D8). The reply is fenced, bare, or broken: a fence that never
    closes, prose with no diagram, a first line that opens no diagram kind. The
    reason is one plain sentence for the person; nothing is guessed at."""
    text = (reply or "").strip()
    fenced_body = _fence_body(text)
    if fenced_body is not None:
        body = fenced_body.strip("\n")
    elif "```" in text:
        return "", "The model's diagram was cut off before the fence closed. Try again, or describe fewer steps."
    else:
        body = text
    first = next((line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("%%")), "")
    if not _HEADERS.match(first):
        return "", "The model answered in words, not a diagram. Try again, or describe the steps in order."
    if len(body.splitlines()) < 2:
        return "", "The model's diagram had nothing in it. Try again with more detail."
    if len(body) > MAX_SOURCE:
        return "", "The model's diagram is too long to open as blocks. Describe fewer steps."
    return body.rstrip() + "\n", ""


# --- from notes ------------------------------------------------------------------------


def _note_day(note: dict) -> date | None:
    """A note's day: an ISO `written` (the Writing room's sources) or
    `created_at`, else the chat route's `written` words (`composer_read._written`)."""
    for raw in (note.get("written"), note.get("created_at")):
        if isinstance(raw, date):
            return raw
        if raw and re.match(r"\d{4}-\d{2}-\d{2}", str(raw)):
            return date.fromisoformat(str(raw)[:10])
    from tessellate.ai import composer_read

    return composer_read._written(note)


def _day_words(day: date) -> str:
    return f"{day.day} {('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[day.month - 1]} {day.year}"


def _notes_flowchart(named: list) -> Diagram:
    """The first note's steps, else the notes themselves in the order written."""
    for _name, note, _day in named:
        found = steps(note.get("content") or "")
        if found:
            return flowchart(found)
    return flowchart([name for name, _n, _d in sorted(named, key=lambda row: row[2] or date.max)])


def _notes_branches(named: list) -> list[tuple[int, str]]:
    """Each note a branch, its key points one step under it."""
    from tessellate.ai import composer_write

    branches: list[tuple[int, str]] = []
    for name, note, _day in named:
        branches.append((1, name))
        points = composer_write._note_points(note.get("content") or "", name)[:BRANCH_POINTS]
        branches.extend((2, p) for p in points)
    return branches


def _named(notes: list[dict]) -> list[tuple[str, dict, date | None]]:
    """(name, note, day) for each note that has words."""
    from tessellate.ai import composer_write

    return [(composer_write.note_name(n, size=NAME_CHARS), n, _note_day(n)) for n in notes if (n.get("content") or "").strip()]


def from_notes(notes: list[dict], want: str | None, subject: str = "") -> Diagram | None:
    """A diagram of several notes: their days as a timeline, or the subject
    as a mind map with each note a branch and its key points under it."""
    named = _named(notes)
    if not named:
        return None
    #: One note that is a list of steps or tasks, asked for by no shape, is a flow.
    if want == "flowchart" or (not want and len(named) == 1 and steps(named[0][1].get("content") or "")):
        return _notes_flowchart(named)
    days = [row for row in named if row[2]]
    if want == "timeline" and days:
        days.sort(key=lambda row: row[2])
        return timeline([(_day_words(day), name) for name, _n, day in days], subject)
    return mindmap(subject or "My notes", _notes_branches(named))


# --- the door --------------------------------------------------------------------------


def _drawn(text: str, want: str | None) -> tuple[Diagram | None, str]:
    """The diagram of the shape asked for, else the first shape the text has."""
    by_shape = {
        "flowchart": lambda: (lambda s: flowchart(s) if s else None)(steps(text)),
        "timeline": lambda: (lambda d: timeline(d) if len(d) >= 2 else None)(dated(text)),
        "mindmap": lambda: (lambda r: mindmap(*r) if r[1] else None)(tree(text)),
    }
    if want:
        made = by_shape[want]()
        if made is not None:
            return made, ""
    for shape in ("flowchart", "timeline", "mindmap"):
        made = by_shape[shape]()
        if made is not None:
            missed = {"flowchart": "steps", "timeline": "dates"}.get(want or "", "")
            why = f"There were no {missed} to draw a {want} from, so this is a {shape}." if missed else ""
            return made, why
    return None, ""


def diagram(text: str, *, want: str | None = "", notes: list[dict] | None = None, subject: str = "") -> Diagram | None:
    """The diagram for `text`, or for `notes` when there is no text; None
    when neither has anything to draw."""
    made, why = _drawn(text, want) if (text or "").strip() else (None, "")
    if made is None and notes:
        made = from_notes(notes, want, subject)
    if made is None:
        return None
    said = {"flowchart": "a flowchart", "timeline": "a timeline", "mindmap": "a mind map"}[made.shape]
    made.note = why or f"Drew {said} from your words by plain rule, with no model. A saved note shows it as a picture."
    return made


def drafted(text: str, instruction: str, sources: list[dict] | None) -> tuple[str, str]:
    """The Writing room's diagram pass: (the fenced diagram, the line to say),
    or ("", why) when there is nothing to draw."""
    made = diagram(text, want=wanted(instruction), notes=sources)
    if made is None:
        return "", "There's nothing here to draw yet: write a few steps, dated lines or points first."
    return fenced(made), made.note


# --- from Chat and Ask -----------------------------------------------------------------

#: Words of a diagram request that are not its subject.
_NOT_SUBJECT = frozenset(
    """make draw turn create show give build generate render convert put map sketch can could would you do please me
    a an the of my our on about as into in for from with all this that it these those notes note diagram diagrams
    flowchart flow chart charts mind mindmap timeline time line graph mermaid concept spider steps step process""".split()
)
_REFERS = re.compile(r"\b(?:this|that|it|these|the (?:answer|above|last (?:answer|reply)))\b", re.I)
_SUBJECT_AFTER = re.compile(r"\b(?:on|about|for|of)\s+(?:my\s+)?(?:notes?\s+(?:on|about)\s+)?([a-z0-9][a-z0-9 '\-]{1,60})$", re.I)


def _given_text(question: str, previous: str, opened: str) -> str:
    """The text a "turn this into a flowchart" means: what follows a colon
    or a line break in the message, else the open note, else the last answer."""
    cut = re.search(r"[:\n]", question)
    head, rest = (question[: cut.start()], question[cut.end():]) if cut else (question, "")
    if len(rest.split()) >= 4:
        return rest.strip()
    if _REFERS.search(head):
        return (opened or previous or "").strip()
    return ""


def _subject(question: str) -> tuple[str, list[str]]:
    """(the subject as said, its words) of "a diagram of my notes on X"."""
    bare = re.sub(r"[?.!]+$", "", question.strip())
    found = _SUBJECT_AFTER.search(bare)
    said = found.group(1).strip() if found else ""
    words = [w for w in re.findall(r"[a-z0-9']+", (said or bare).lower()) if w not in _NOT_SUBJECT and len(w) > 2]
    said = re.sub(r"\s+notes?$", "", said)
    if not said or not words:
        said = " ".join(words)
    return said, words


def _about(notes: list[dict], words: list[str]) -> list[dict]:
    """The notes that say a subject word (its first five letters); with no
    subject word ("my notes", all of them), the first few notes."""
    if not words:
        return notes[:8]
    stems = [w[:5] for w in words]
    #: Its title and tags too: the notes found for "running" by their tag ("Ran 5 km") are on it (L158).
    said = [" ".join([str(n.get("title") or ""), str(n.get("content") or ""), " ".join(map(str, n.get("tags") or []))]) for n in notes]
    return [n for n, words in zip(notes, said, strict=True) if any(re.search(rf"\b{re.escape(s)}", words, re.I) for s in stems)][:8]


def _notes_lead(count: int, said: str) -> str:
    on = f" on {said}" if said else ""
    which = f"your {count} notes{on}" if count != 1 else f"your note{on}"
    return f"Here are {which} as {{shape}}, drawn by plain rule with no model." if count != 1 else f"Here is {which} as {{shape}}, drawn by plain rule with no model."


def answer(question: str, notes: list[dict], *, previous: str = "", opened: str = "") -> dict | None:
    """A Chat or Ask turn that asks for a diagram, answered with one; None
    when the question asks for none or there is nothing to draw. The shape of
    a composed result (`composer.compose`), with no grounding rows: the
    diagram quotes the notes' words, each named by its note."""
    if not asks(question):
        return None
    want = wanted(question)
    text = _given_text(question, previous, opened)
    if text:
        made = diagram(text, want=want)
        lead = "Here it is as {shape}, drawn by plain rule with no model."
    else:
        if _REFERS.search(question) and not _SUBJECT_AFTER.search(question):
            return None  # "turn this into a flowchart" with nothing to turn
        said, words = _subject(question)
        chosen = _about([n for n in notes if (n.get("content") or "").strip()], words)
        made = diagram("", want=want, notes=chosen, subject=said[:1].upper() + said[1:] if said else "")
        lead = _notes_lead(len(chosen), said)
    if made is None:
        return None  # nothing on the subject: the ordinary answer, not a drawing of other notes
    shape = {"flowchart": "a flowchart", "timeline": "a timeline", "mindmap": "a mind map"}[made.shape]
    return {"text": lead.format(shape=shape) + "\n\n" + fenced(made), "grounding": [], "answered": True, "shape": "diagram", "next": []}
