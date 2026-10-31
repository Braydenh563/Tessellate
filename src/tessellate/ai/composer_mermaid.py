"""A Mermaid diagram from text or notes, by plain rule (INBOX 1466).

The owner, 2026-10-31: "can it be used to generate mermaid diagrams??". The
app already draws every ```mermaid fence (mermaid-draw.js, in notes, chat,
Ask and documents); this writes the fence, from the shape the words have:

- **steps** (a numbered list, or lines that go "first ... then ... finally")
  are a `flowchart TD`, one box a step, an arrow between each;
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
        out.append(("heading", 0, False, heading.group(1)) if heading else ("line", 0, False, raw.strip()))
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


def steps(text: str) -> list[str]:
    """The steps the text gives, in order: a numbered list's items, else
    sentences or clauses joined by "then", when there are at least three."""
    listed = _listed_steps(_lines(text))
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


def tree(text: str) -> tuple[str, list[tuple[int, str]]]:
    """(root, [(depth, words)]) of a heading with bullets, or of the first
    sentence with the rest as branches."""
    lines = _lines(text)
    root = next((w for kind, _d, _n, w in lines if kind == "heading"), "")
    branches = [(depth, words) for kind, depth, _n, words in lines if kind == "item"]
    branches += [(1, words) for kind, _d, _n, words in lines if kind == "heading" and words != root]
    if not branches:
        said = _sentences(text)
        if not root and said:
            root, said = said[0], said[1:]
        branches = [(1, s) for s in said]
    if not root:
        from tessellate.ai import no_model_text

        root = no_model_text.draft_title(text) or "Notes"
    return root, branches


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
    lines = ["mindmap", f"  root(({label(root)}))"]
    for i, (depth, words) in enumerate(shown):
        lines.append("  " * (depth - top + 2) + f"n{i + 1}[{label(words)}]")
    if more:
        lines.append(f"    n{len(shown) + 1}[{label(f'and {more} more')}]")
    return Diagram("mindmap", "\n".join(lines), 1 + len(shown) + (1 if more else 0))


def fenced(made: Diagram) -> str:
    return f"```mermaid\n{made.source}\n```"


# --- from notes ------------------------------------------------------------------------


def _note_day(note: dict) -> date | None:
    """A note's day: an ISO `written` (the Writing room's sources) or
    `created_at`, else the chat route's `written` words (`composer._written`)."""
    for raw in (note.get("written"), note.get("created_at")):
        if isinstance(raw, date):
            return raw
        if raw and re.match(r"\d{4}-\d{2}-\d{2}", str(raw)):
            return date.fromisoformat(str(raw)[:10])
    from tessellate.ai import composer

    return composer._written(note)


def _day_words(day: date) -> str:
    return f"{day.day} {('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[day.month - 1]} {day.year}"


def _notes_flowchart(named: list) -> Diagram:
    """The first note's steps, else the notes themselves in the order written."""
    for _name, note, _day in named:
        found = steps(note.get("content") or "")
        if found:
            return flowchart(found)
    return flowchart([name for name, _n, _d in sorted(named, key=lambda row: row[2] or date.max)])


def from_notes(notes: list[dict], want: str | None, subject: str = "") -> Diagram | None:
    """A diagram of several notes: their days as a timeline, or the subject
    as a mind map with each note a branch and its key points under it."""
    from tessellate.ai import composer_write

    named = [(composer_write.note_name(n, size=NAME_CHARS), n, _note_day(n)) for n in notes if (n.get("content") or "").strip()]
    if not named:
        return None
    if want == "flowchart":
        return _notes_flowchart(named)
    days = [row for row in named if row[2]]
    if want == "timeline" and days:
        days.sort(key=lambda row: row[2])
        return timeline([(_day_words(day), name) for name, _n, day in days], subject)
    branches: list[tuple[int, str]] = []
    for name, note, _day in named:
        branches.append((1, name))
        points = composer_write._note_points(note.get("content") or "", name)[:BRANCH_POINTS]
        branches.extend((2, p) for p in points)
    return mindmap(subject or "My notes", branches)


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
    return [n for n in notes if any(re.search(rf"\b{re.escape(s)}", str(n.get("content") or ""), re.I) for s in stems)][:8]


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
