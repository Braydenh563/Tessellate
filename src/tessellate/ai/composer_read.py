"""Reading a note into what an answer may quote: sentences and list items
(`Sentence`, `NoteView`, `read_note`), a picture's reading, a note's title.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.read_note` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from datetime import date

from tessellate.ai import composer_frame, composer_tables, realise, recognise as rec
from tessellate.ai.composer_ask import _MONTHS, _MONTH_INDEX, _WEEKDAYS, _words
from tessellate.core.docmeta import block_end


#: A quote longer than this is cut at a word with an ellipsis, which says it
#: was cut. Long enough for almost every sentence a person writes in a note.
MAX_QUOTE_CHARS = 280


#: A note with no heading is named by its first words, as the Sources panel
#: names it: the person's words, and enough of them to recognise the note.
UNTITLED_WORDS = 6


# --- the notes, as sentences ---------------------------------------------------


@dataclass
class Sentence:
    """One quotable unit of a note: a sentence of prose or one list item."""

    note_id: int
    rank: int
    start: int
    end: int
    text: str
    words: list[str]
    #: "prose", "item", "task" (a checklist item; `done` says which),
    #: "picture" (the app's caption of a picture in the note) or
    #: "picture_text" (the words the app read in it).
    kind: str = "prose"
    done: bool | None = None
    order: int = 0
    score: float = 0.0
    #: How far a list item is indented under the one before it (a map's
    #: children, an outline's sub-points); 0 for everything else.
    depth: int = 0
    #: Sentences of other notes that say the same thing, dropped so the answer
    #: says it once, and counted: "(Your notes say this three times.)".
    echoes: list = field(default_factory=list)

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.note_id, self.order, self.start)


@dataclass
class NoteView:
    """A retrieved note, read once: its name, the day it was written, its units."""

    note: dict
    rank: int
    title: str
    written: date | None
    sentences: list[Sentence] = field(default_factory=list)
    words: set[str] = field(default_factory=set)
    title_words: set[str] = field(default_factory=set)
    #: Its tags and category: never quoted, but what the person filed it
    #: under says what it is about ("Reading list", tagged #books, is about
    #: books without saying the word).
    filed_words: set[str] = field(default_factory=set)
    #: Whether the note has a heading. One without is never named by its first
    #: words (INBOX 741): the quote already says them, and "your note starting
    #: with ... says" was the whole complaint. It is cited by its day instead.
    titled: bool = False
    #: What kind of source it is (decision 37): "note", "board", "map",
    #: "document", "file" or "web". Said in its citation and on its row, so
    #: the page opens it in its own place.
    kind: str = "note"

    @property
    def id(self) -> int:
        return self.note["id"]


#: Only a heading's marks: the text after them is read in code, as a pattern
#: running on to the line's end backtracks over runs of whitespace (CodeQL).
_HEADING_LEAD = re.compile(r"[ \t]{0,3}#{1,6}[ \t]+")


#: A list line, or a checkbox written with no bullet ("[ ] Buy mint.", as
#: pasted from many apps; stress run 2026-10-30 read those as prose, so an
#: open task answered "did I" with "Yes").
_ITEM = re.compile(r"^(\s*(?:[-*+]|\d{1,3}[.)])\s+|\s*(?=\[[ xX]\]\s))(\[[ xX]\]\s+)?")


#: Where one sentence ends and the next begins: a stop (and the quote mark or
#: bracket closing it), a space, and a capital or a digit. Misses some
#: abbreviations; never merges two sentences, the safer direction here.
#: A full-width stop ends a sentence with no space after it (audit 1031 C10).
_SPLIT = re.compile(r"(?:([.!?][\"”’)]?)\s+(?=[\"“‘(]?[A-Z0-9])|([。！？][」』”’)]?)\s*)")


#: The lead-ins a person opens a sentence with that carry no claim, the tested
#: list (INBOX 725: "Trim lead-ins ("So basically,") from quotes with a tested
#: list"). `LEAD_INS` are taken off only with the comma or colon after them,
#: so "But the API ..." keeps its contrast and "Now the list scrolls" keeps
#: its "now"; `LEAD_INS_BARE` mean nothing even without one ("Basically the
#: hills are steep" says what "The hills are steep" says). Several in a row
#: ("Ok so basically,") come off together.
LEAD_INS = (
    "so basically", "ok so", "okay so", "right so", "so", "also", "anyway", "anyhow", "plus", "oh", "well",
    "ok", "okay", "right", "basically", "honestly", "and", "but", "then", "now", "by the way", "btw", "fyi",
    "in any case", "to be honest", "tbh", "note to self", "quick note", "update", "edit",
    *composer_tables.EXTRA_LEAD_INS,
)


LEAD_INS_BARE = (
    "so basically", "basically", "honestly", "to be honest", "tbh", "btw", "fyi", "frankly", "essentially", "personally",
    "genuinely", "seriously", "apparently", "evidently", "simply", "literally", "just so you know", "for what it is worth",
    "to be fair", "in fairness", "to be clear", "just to say",
)


_LEAD_IN = "|".join(re.escape(w) for w in sorted(LEAD_INS, key=len, reverse=True))


_LEAD_IN_BARE = "|".join(re.escape(w) for w in sorted(LEAD_INS_BARE, key=len, reverse=True))


#: Compiled on first use, for the cold-import budget (`recognise._window_words`).
@functools.cache
def _discourse() -> re.Pattern[str]:
    return re.compile(
        rf"^(?:(?:{_LEAD_IN})(?:\s+(?:{_LEAD_IN}))*\s*[,:]\s+|(?:{_LEAD_IN_BARE})\s+(?=(?-i:[a-z])))+(?=\S)",
        re.I,
    )


_WRITTEN = re.compile(r"(\d{1,2}) (" + "|".join(_MONTHS) + r") (\d{4})")


_MARKS = re.compile(r"[*_`]")


def _written(note: dict) -> date | None:
    """The day the note was written, from the route's `written` words
    ("Wednesday 23 September 2026, 09:40") or an ISO `created_at`."""
    raw = str(note.get("created_at") or "")
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    match = _WRITTEN.search(str(note.get("written") or ""))
    if not match:
        return None
    try:
        return date(int(match.group(3)), _MONTH_INDEX[match.group(2).lower()], int(match.group(1)))
    except ValueError:
        return None


def _heading_text(line: str) -> str | None:
    """A heading line's text ("" for a bare "# "), or None for another line."""
    lead = _HEADING_LEAD.match(line)
    return line[lead.end() :].rstrip("\r\n").strip() if lead else None


#: A line that is only bold ("**After making an initial connection**") is a
#: heading the person made without "#" (INBOX 1420): a name, never a sentence.
_BOLD_LINE = re.compile(r"[ \t]{0,3}(\*\*|__)(?=\S)([^*_\n]{1,80}?)\1:?[ \t]*\r?\n?$")


#: "Follow- Up" as typed on a phone: the hyphen's word goes on (INBOX 1420).
_SPLIT_HYPHEN = re.compile(r"(?<=[A-Za-z])- (?=[A-Z][a-z])")


_BOLD_STARS = re.compile(r"\*\*(?=\S)([^*\n]+?)(?<=\S)\*\*")


_BOLD_UNDERS = re.compile(r"__(?=\S)([^_\n]+?)(?<=\S)__")


#: A short first line ending in a colon, with lines under it: "Ice Breakers:"
#: over its list is the note's name (INBOX 1420).
_COLON_TITLE = re.compile(r"([^\s:.!?][^:.!?\n]{0,48}?):$")


def bold_line(line: str) -> str | None:
    """A wholly bold line's words, or None for another line."""
    found = _BOLD_LINE.match(line)
    return found.group(2).strip() if found else None


def plain_words(text: str) -> str:
    """A note's words without its emphasis marks or a split hyphen: what the
    page shows, which is what an answer says."""
    #: One pass per mark, each inner run unable to cross its own mark: linear
    #: on a line of unclosed marks (CodeQL's polynomial-regex alert).
    text = _BOLD_STARS.sub(r"\1", _BOLD_UNDERS.sub(r"\1", text)).replace("**", "")
    return _SPLIT_HYPHEN.sub("-", text)


def _title(content: str) -> tuple[str, int]:
    """The note's name and where its body starts: its first heading, or, with
    none, its first few words (the body then starts at the top, so those words
    are quotable too)."""
    end = content.find("\n")
    first = content if end == -1 else content[:end]
    heading = _heading_text(first)
    if heading is None:
        heading = bold_line(first)
    if heading is None and end != -1 and content[end:].strip():
        colon = _COLON_TITLE.match(first.strip(" \t"))
        heading = colon.group(1) if colon and len(colon.group(1).split()) <= 6 else None
    if heading is not None:
        name = plain_words(_MARKS.sub("", heading).strip().strip("#").strip())
        if name:
            return name, len(content) if end == -1 else end
    words = _MARKS.sub("", first.strip().lstrip("-*+> ")).split()
    if not words:
        return "", 0
    if len(words) <= UNTITLED_WORDS:
        return " ".join(words).rstrip(".,;:!?"), 0
    #: Cut where `realise.cut_title` cuts: never on "at", "the" or "and".
    return " ".join(realise.drop_dangling(words[:UNTITLED_WORDS])).rstrip(".,;:!?") + "…", 0


def _depth(line: str) -> int:
    """A list item's nesting: two columns of indent a level, tabs as four."""
    flat = line.expandtabs(4).rstrip("\r\n")
    return min((len(flat) - len(flat.lstrip(" "))) // 2, 4)


def _unit(view: NoteView, content: str, start: int, end: int, kind: str, done: bool | None) -> Sentence | None:
    """One sentence, trimmed as the rule allows, its offsets moved to match."""
    raw = content[start:end]
    start += len(raw) - len(raw.lstrip())
    raw = raw.strip()
    discourse = _discourse().match(raw)
    if discourse:
        start += discourse.end()
        raw = raw[discourse.end():]
    end = start + len(raw)
    text = plain_words(" ".join(raw.split()))
    if not text:
        return None
    if len(text) > MAX_QUOTE_CHARS:
        cut = text[:MAX_QUOTE_CHARS]
        space = cut.rfind(" ")
        text = (cut[:space] if space > MAX_QUOTE_CHARS // 2 else cut).rstrip(" ,;:") + "…"
    if text[0].islower():
        text = text[0].upper() + text[1:]
    words = _words(text)
    #: A fragment of one or two words ("Booked.", "Ideas") is not a claim and
    #: reads as noise quoted on its own. A list item is read inside its list,
    #: where "Crash reporting" is a whole entry.
    #: A short line with a figure ("Rent 650.", "Mum 0412 555 019") or a
    #: "Label: value" shape is a fact, not noise: budgets, numbers and lists
    #: of values are written that way (audit 1028 E5).
    #: A script with no spaces is one "word" to `split`: its length is its characters.
    thin = len(text.split()) < 3 and not (composer_frame.NON_LATIN.search(text) and len(text) >= 6)
    if not words or (kind == "prose" and thin and not _short_fact(text)):
        return None
    return Sentence(view.id, view.rank, start, end, text, words, kind, done)


#: A rating or a verdict is the whole review in a book or film note: "9/10",
#: "Loved it" (audit 1030 Z11: "did I like Piranesi" never saw either).
_SHORT_VERDICT = re.compile(
    r"^(?:\d+(?:\.\d)?\s*/\s*(?:5|10)|\d\s*stars?|(?:really\s+|not\s+)?(?:lov|lik|enjoy|hat|dislik)(?:ed|e)\s+(?:it|this|that|them)"
    r"|(?:so\s+|really\s+|not\s+)?(?:good|great|boring|amazing|brilliant|terrible|awful|meh))[.!]?$",
    re.I,
)


def _short_fact(text: str) -> bool:
    """A one- or two-word line that still says something: a word and a
    figure, a label and its value, or a verdict."""
    if _SHORT_VERDICT.match(text.strip()):
        return True
    parts = text.rstrip(".").split()
    if len(parts) < 2:
        return False
    return any(ch.isdigit() for ch in text) or ":" in parts[0]


#: The block `routes_chat._media_readings` adds under a note that is mostly
#: pictures: one line per picture, "- name: shows <caption>; text in it: "..."".
#: The app's own reading of the person's picture counts as from the note
#: (INBOX 725, 7) and is introduced as one: "The picture in **Sketches**
#: shows ...", never as the person's sentence.
_PICTURES_HEAD = "[Pictures in this note"


_PICTURE_TEXT_LEAD = 'text in it: "'


def _picture_groups(line: str) -> dict[str, tuple[str, int]] | None:
    """The caption and the text one picture line holds, each with where it
    starts in the line, or None for another line. Read by hand: a pattern for
    it backtracks over runs of whitespace (CodeQL)."""
    dash = len(line) - len(line.lstrip())
    colon = line.find(":", dash)
    if line[dash : dash + 1] != "-" or not line[dash + 1 : dash + 2].isspace() or colon < dash + 3:
        return None
    if not line[colon + 1 : colon + 2].isspace():
        return None
    at = colon + 1 + len(line[colon + 1 :]) - len(line[colon + 1 :].lstrip())
    end = len(line.rstrip())
    end -= line[:end].endswith("]")
    rest, groups = line[at:end], {"caption": ("", 0), "text": ("", 0)}
    lead = rest.find(_PICTURE_TEXT_LEAD) if rest.endswith('"') else -1
    if lead != -1 and lead + len(_PICTURE_TEXT_LEAD) < len(rest) - 1:
        groups["text"] = (rest[lead + len(_PICTURE_TEXT_LEAD) : -1], at + lead + len(_PICTURE_TEXT_LEAD))
        rest = rest[:lead].rstrip()
        rest = rest[:-1] if rest.endswith(";") else rest
    if rest.startswith("shows ") and len(rest) > len("shows "):
        groups["caption"] = (rest[len("shows ") :], at + len("shows "))
    elif rest:
        return None
    return groups


#: A captioning model's frame around what a picture shows ("The image
#: contains a text excerpt ..."): read past, so the answer says "a text
#: excerpt ..." and never "shows The image shows" (INBOX 787).
_CAPTION_FRAME = re.compile(
    r"^(?:the|this)\s+(?:image|picture|photo|photograph|screenshot)\s+(?:contains|shows|depicts|is of|is)\s+(?=\S)", re.I
)


_LIST_NUMBER = re.compile(r"\d{1,2}[.)]\s")


def _picture_text_breaks(text: str) -> list[tuple[int, int]]:
    """Where a picture's text breaks into lines: a lone "/" with space each side
    (the route joins its lines with " / "), and the space before a "2." of a
    numbered list run into one line ("1. Offline search 2. Tags"). Found run by
    run of whitespace: one pattern for both backtracks over the runs (CodeQL)."""
    runs, breaks, cursor = [m.span() for m in re.finditer(r"\s+", text)], [], 0
    for i, (start, end) in enumerate(runs):
        if start < cursor:
            continue
        if text[end : end + 1] == "/" and i + 1 < len(runs) and runs[i + 1][0] == end + 1:
            breaks.append((start, runs[i + 1][1]))
            cursor = runs[i + 1][1]
        elif _LIST_NUMBER.match(text[end : end + 4]):
            breaks.append((start, end))
    return breaks


def _picture_spans(group: str, text: str) -> list[tuple[int, str]]:
    """The units one picture reading gives, each with its offset in `text`:
    the caption past its frame, the text one line (or list entry) each."""
    if group == "caption":
        frame = _CAPTION_FRAME.match(text)
        return [(frame.end() if frame else 0, text[frame.end():] if frame else text)]
    spans, cursor = [], 0
    for brk in [*_picture_text_breaks(text), None]:
        end = brk[0] if brk else len(text)
        piece = text[cursor:end]
        lead = len(piece) - len(piece.lstrip())
        number = re.match(r"\d{1,2}[.)]\s+", piece[lead:])
        lead += number.end() if number else 0
        spans.append((cursor + lead, piece[lead:].strip()))
        cursor = brk[1] if brk else end
    return spans


def _picture_units(view: NoteView, content: str, line_start: int, line: str) -> None:
    groups = _picture_groups(line.rstrip("\r\n"))
    if not groups:
        return
    for group, kind in (("caption", "picture"), ("text", "picture_text")):
        whole, at = groups[group]
        for offset, text in _picture_spans(group, whole):
            text = text.strip()
            if len(text.split()) < 2:
                continue
            start = line_start + at + offset
            words = _words(text)
            if words:
                view.sentences.append(Sentence(view.id, view.rank, start, start + len(text), text, words, kind))


#: A list line naming a picture file and what it shows.
_PICTURE_ITEM = re.compile(r"^\s*[-*+]\s+[^:\n]{1,120}\.(?:png|jpe?g|gif|webp|heic|avif|bmp|svg)\s*:\s+\S", re.I)


#: The kind a route's row is, from its own `kind` or the category the route
#: gives a source that is not a note.
_SOURCE_CATEGORIES = {"document": "document", "file": "file", "mind map": "map", "board": "board", "web page": "web"}


def _distinct_ids(notes: list[dict]) -> list[dict]:
    """The sources with an id each answer can key them by: a document or a
    map whose id is also a note's (they live in other tables) is keyed apart,
    its own id kept as `source_id` for its row."""
    taken = {n.get("id") for n in notes if source_kind(n) == "note"}
    out = []
    for i, note in enumerate(notes):
        if source_kind(note) != "note" and note.get("id") in taken:
            note = {**note, "source_id": note.get("id"), "id": -(i + 1) * 1_000_003}
        out.append(note)
    return out


def source_kind(note: dict) -> str:
    """"note", "board", "map", "document", "file" or "web" (decision 37)."""
    kind = str(note.get("kind") or "").strip().lower()
    if kind in ("note", "board", "map", "document", "file", "web"):
        return kind
    return _SOURCE_CATEGORIES.get(str(note.get("category") or "").strip().lower(), "note")


def _not_prose(line: str, stripped: str) -> bool:
    """A heading, a bold-only line, a picture or a table row: no sentence of the note's."""
    return _heading_text(line) is not None or bold_line(line) is not None or stripped.startswith(("![", "|"))


def read_note(note: dict, rank: int) -> NoteView | None:
    """A note as its units: prose split into sentences, each list item one."""
    content = str(note.get("content") or "")
    if not content.strip() or note.get("id") is None:
        return None
    #: A note that opens with a properties block ("---", "tags: [meeting]",
    #: "---") is read from after it: its name and every quote start at the
    #: note's words, never at "---" (audit 1029 X19). Offsets stay the
    #: content's own.
    front = block_end(content)
    #: And from its first line with words in it: the blank line people leave
    #: after the closing fence must not leave the note without a name.
    front += len(content[front:]) - len(content[front:].lstrip("\r\n"))
    title, body_start = _title(content[front:])
    titled = bool(title) and body_start > 0
    body_start = front + body_start
    view = NoteView(note=note, rank=rank, title=title, written=_written(note), titled=titled, kind=source_kind(note))
    if view.kind != "note" and not view.titled and title:
        #: A document or a map arrives as its title, a blank line, its text:
        #: its first line is its name, never a sentence of it.
        view.titled = True
        body_start = front + len(content[front:].split("\n", 1)[0])
    view.title_words = set(_words(title))
    filed = [str(t) for t in (note.get("tags") or [])] + [str(note.get("category") or "")]
    view.filed_words = set(_words(" ".join(filed)))
    view.words = set(_words(content))
    in_fence = False
    in_pictures = False
    offset = 0
    for line in content.splitlines(keepends=True):
        line_start, offset = offset, offset + len(line)
        if line_start < body_start:
            continue
        stripped = line.strip()
        if stripped.startswith(_PICTURES_HEAD):
            in_pictures = True
            continue
        if in_pictures:
            _picture_units(view, content, line_start, line)
            in_pictures = not stripped.endswith("]")
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or _not_prose(line, stripped):
            continue
        _line_units(view, content, line_start, line)
    for i, sentence in enumerate(view.sentences):
        sentence.order = i
    return view


def _line_units(view: NoteView, content: str, line_start: int, line: str) -> None:
    """The units of one body line: a picture's caption, a list item, or prose sentences."""
    line_end = line_start + len(line.rstrip("\r\n"))
    if _PICTURE_ITEM.match(line):
        #: "- shed.jpg: shows a wet wooden roof": a picture's caption
        #: listed in the note is content, read as the picture's
        #: (decision 37; the owner: "note captions arent counted").
        _picture_units(view, content, line_start, line)
        return
    item = _ITEM.match(line)
    if item:
        box = item.group(2)
        unit = _unit(
            view, content, line_start + item.end(), line_end,
            "task" if box else "item",
            None if not box else box.strip("[] \t").lower() == "x",
        )
        if unit:
            unit.depth = _depth(line)
            view.sentences.append(unit)
        return
    body = line_start + (len(line) - len(line.lstrip(" >")))
    cursor = body
    for match in _SPLIT.finditer(content, body, line_end):
        unit = _unit(view, content, cursor, match.end(1) if match.group(1) else match.end(2), "prose", None)
        if unit:
            view.sentences.append(unit)
        cursor = match.end()
    unit = _unit(view, content, cursor, line_end, "prose", None)
    if unit:
        view.sentences.append(unit)


# --- scoring --------------------------------------------------------------------

_NUMBER_CUE = re.compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
    r"hundred|thousand|dozen|half|twice|double)\b",
    re.I,
)


_CAUSE_CUE = re.compile(r"\b(because|since|so that|which is why|that is why|due to|caused|the reason|means)\b", re.I)


_WHERE_CUE = re.compile(
    r"\b(?:in|at|near|on|by|from|to) (?:the )?[A-Z][\w-]+|\b(street|road|avenue|address|room|floor|hotel|station|"
    r"shop|office|cafe|restaurant|square|park|airport|flat|house|apartment|upstairs|downstairs|drawer|shelf|garage)\b",
)


_WHO_CUE = re.compile(r"\b(people|person|someone|team|testers?|users?|he|she|they|asked|said)\b", re.I)


def _cue(shape: str, text: str) -> float:
    """What the question's shape looks for in an answer: a date for a "when",
    a number for a "how many", a person for a "who"."""
    if shape == "when":
        return 1.2 if rec.looks_dated(text) else 0.0
    if shape == "count":
        return 1.2 if _NUMBER_CUE.search(text) else 0.0
    if shape == "explain":
        #: "because" is never written here, but a sentence of the note's own
        #: that says "because" or "so that" is what a "why" is asking for.
        return 0.6 if _CAUSE_CUE.search(text) else 0.0
    if shape == "where":
        return 1.0 if _WHERE_CUE.search(text) else 0.0
    if shape == "who":
        names = [
            w for w in re.findall(r"(?<=\s)[A-Z][a-z]+", text)
            if w.lower() not in _WEEKDAYS and w.lower() not in _MONTH_INDEX
        ]
        return 0.8 if names or _WHO_CUE.search(text) else 0.0
    return 0.0
