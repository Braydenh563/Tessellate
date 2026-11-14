"""Reading a note into what an answer may quote: sentences and list items
(`Sentence`, `NoteView`, `read_note`), a picture's reading, a note's title.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.read_note` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import functools
import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import date

from tessellate.ai import composer_frame, composer_tables, realise, recognise as rec
from tessellate.ai.composer_ask import _MONTHS, _words
from tessellate.core.docmeta import block_end
from tessellate.core.lazyre import lazy_compile


#: A quote longer than this is cut at a word with an ellipsis, which says it
#: was cut. Long enough for almost every sentence a person writes in a note.
MAX_QUOTE_CHARS = 280


#: A note with no heading is named by its first words, as the Sources panel
#: names it: the person's words, and enough of them to recognise the note.
UNTITLED_WORDS = 6


# --- the notes, as sentences ---------------------------------------------------


_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


_MONTH_INDEX = {name.lower(): i + 1 for i, name in enumerate(_MONTHS)}


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
    #: Whether the sentence's own words match the question; False when it
    #: scores only on its note's name or tags (`composer_select.relevance`).
    own: bool = True
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
_HEADING_LEAD = lazy_compile(r"[ \t]{0,3}#{1,6}[ \t]+")


#: A list line, or a checkbox written with no bullet ("[ ] Buy mint.", as
#: pasted from many apps; stress run 2026-10-30 read those as prose, so an
#: open task answered "did I" with "Yes").
#: A line indented under a list item, carrying on its words.
_CONTINUES = lazy_compile(r"^(?:\t| {2,})\S")


_ITEM = lazy_compile(r"^(\s*(?:[-*+]|\d{1,3}[.)])\s+|\s*(?=\[[ xX]\]\s))(\[[ xX]\]\s+)?")


#: Where one sentence ends and the next begins: a stop (and the quote mark or
#: bracket closing it), a space, and a capital or a digit. Misses some
#: abbreviations; never merges two sentences, the safer direction here.
#: A full-width stop ends a sentence with no space after it (audit 1031 C10).
#: A chat sign-off closes a sentence the writer did not capitalise after
#: ("...at work lol. need to lock-in"), so a stop after one splits too
#: (INBOX 1665 f: two sentences run into "at work need to lock-in").
_SPLIT = lazy_compile(
    r"(?:([.!?][\"”’)]?)\s+(?=[\"“‘(]?[A-Z0-9])|([。！？][」』”’)]?)\s*"
    r"|(\b(?:lol|lmao|lmfao|rofl|haha+|hehe+)[.!?]+)\s+(?=[a-z]))")


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


#: Compiled on first use, for the cold-import budget (`recognise_windows._window_words`).
@functools.cache
def _discourse() -> re.Pattern[str]:
    return re.compile(
        rf"^(?:(?:{_LEAD_IN})(?:\s+(?:{_LEAD_IN}))*\s*[,:]\s+|(?:{_LEAD_IN_BARE})\s+(?=(?-i:[a-z])))+(?=\S)",
        re.I,
    )


_WRITTEN = lazy_compile(r"(\d{1,2}) (" + "|".join(_MONTHS) + r") (\d{4})")


_MARKS = lazy_compile(r"[*_`]")


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
_BOLD_LINE = lazy_compile(r"[ \t]{0,3}(\*\*|__)(?=\S)([^*_\n]{1,80}?)\1:?[ \t]*\r?\n?$")


#: "Follow- Up" as typed on a phone: the hyphen's word goes on (INBOX 1420).
_SPLIT_HYPHEN = lazy_compile(r"(?<=[A-Za-z])- (?=[A-Z][a-z])")


_BOLD_STARS = lazy_compile(r"\*\*(?=\S)([^*\n]+?)(?<=\S)\*\*")


_BOLD_UNDERS = lazy_compile(r"__(?=\S)([^_\n]+?)(?<=\S)__")


#: A short first line ending in a colon, with lines under it: "Ice Breakers:"
#: over its list is the note's name (INBOX 1420).
_COLON_TITLE = lazy_compile(r"([^\s:.!?][^:.!?\n]{0,48}?):$")


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
        #: A short plain first line over the body names it the way the frame
        #: names it ("Legs day", INBOX 1515: one reader for every shape).
        heading = heading or composer_frame.title_line(content) or None
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


#: A subordinating word and a gerund open a clause that needs a main clause.
_FRAGMENT_OPEN = lazy_compile(r"(?:after|before|when|while|once|until|upon|by|without|instead of|prior to|in order to|on)\s+[a-z]+ing\b", re.I)
_OWN_SUBJECT = lazy_compile(r"\b(?:i|we|you|he|she|they|it|there)\b|[,;:]", re.I)


def _dependent_fragment(text: str) -> bool:
    """A clause with no main clause: opens "after/before/when ... -ing", has no
    comma and no subject of its own, and is short. "After making coffee, I
    left." and "Before leaving I locked up." are whole sentences."""
    words = text.rstrip(".!? ").split()
    return len(words) <= 10 and bool(_FRAGMENT_OPEN.match(text)) and not _OWN_SUBJECT.search(text)


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
    #: "After making an initial connection." has no main clause: it is half of
    #: a sentence a list finishes, and quoted alone it reads as a whole one
    #: (INBOX 1561 d).
    if kind == "prose" and _dependent_fragment(text):
        return None
    return Sentence(view.id, view.rank, start, end, text, words, kind, done)


#: A rating or a verdict is the whole review in a book or film note: "9/10",
#: "Loved it" (audit 1030 Z11: "did I like Piranesi" never saw either).
_SHORT_VERDICT = lazy_compile(
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
    #: "Skipped meditation.": a past verb and what it was done to (R9-2).
    if len(parts) == 2 and re.fullmatch(r"[A-Za-z]{4,}ed", parts[0]) and re.fullmatch(r"[a-z]{6,}", parts[1]):
        return True
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
_CAPTION_FRAME = lazy_compile(
    r"^(?:(?:the|this)\s+(?:image|picture|photo|photograph|screenshot)\s+(?:contains|shows|depicts|is of|is)"
    #: "A photo of a grassy hill": said "shows a grassy hill", never "shows A photo of" (INBOX 1555).
    r"|(?:an?|the|this)\s+(?:image|picture|photo|photograph)\s+of)\s+(?=\S)", re.I
)


_LIST_NUMBER = lazy_compile(r"\d{1,2}[.)]\s")


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
_PICTURE_ITEM = lazy_compile(r"^\s*[-*+]\s+[^:\n]{1,120}\.(?:png|jpe?g|gif|webp|heic|avif|bmp|svg)\s*:\s+\S", re.I)


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
    """A heading, a bold-only line or a picture: no sentence of the note's. A
    table row is read apart (`_table_row`), not skipped."""
    return _heading_text(line) is not None or bold_line(line) is not None or stripped.startswith("![")


_TABLE_RULE = lazy_compile(r"^\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?$")


def is_table_rule(stripped: str) -> bool:
    """The `|---|---|` line under a table's header."""
    return stripped.startswith(("|", "-", ":")) and bool(_TABLE_RULE.match(stripped))


def _skipped(view: NoteView, content: str, lines: list[str], at: int, line_start: int, in_fence: bool) -> bool:
    """Whether line `at` is no prose of the note's: inside a fence, blank, a
    heading or picture, or a table row (read here as an item of its own)."""
    line = lines[at]
    stripped = line.strip()
    if in_fence or not stripped:
        return True
    if stripped.startswith("|"):
        ahead = lines[at + 1].strip() if at + 1 < len(lines) else ""
        _table_row(view, content, line_start, line, header=is_table_rule(ahead))
        return True
    return _not_prose(line, stripped)


def _table_row(view: NoteView, content: str, line_start: int, line: str, header: bool) -> None:
    """One row of a table is one item ("Bread £2.50"), the way a list item is:
    its cells are what the note says, and a price asked for sits in the row
    (round 2 E1: a table was "only a title"). The header row and the rule
    under it name the columns and are no claim."""
    stripped = line.strip()
    if header or is_table_rule(stripped):
        return
    lead = len(line) - len(line.lstrip())
    inner_start = line_start + lead + 1
    inner_end = line_start + len(line.rstrip()) - (1 if stripped.endswith("|") else 0)
    unit = _unit(view, content, inner_start, inner_end, "item", None)
    if unit:
        unit.text = " ".join(c for c in (cell.strip() for cell in unit.text.split("|")) if c)
        unit.words = _words(unit.text)
        view.sentences.append(unit)


def _wrap_item(view: NoteView, content: str, line_start: int, line: str, item_open: tuple[int, int, str, bool | None]) -> bool:
    """A list item wrapped onto an indented line ("- hub-finish-ui and" /
    "  O47-merge-wip are in main") is one item, not an item and a sentence cut
    at the wrap (INBOX 1602). True when `line` was taken into the item."""
    if not _CONTINUES.match(line) or _ITEM.match(line):
        return False
    at, first, kind, done = item_open
    joined = _unit(view, content, first, line_start + len(line.rstrip("\r\n")), kind, done)
    if joined and at < len(view.sentences):
        joined.depth = view.sentences[at].depth
        view.sentences[at] = joined
    return True


def _read_line(view: NoteView, content: str, line_start: int, line: str, item_open: tuple[int, int, str, bool | None] | None) -> tuple[int, int, str, bool | None] | None:
    """One body line: taken into the list item above it when it wraps that
    item, else read as units; returns the list item it leaves open, if any."""
    if item_open and _wrap_item(view, content, line_start, line, item_open):
        return item_open
    before = len(view.sentences)
    _line_units(view, content, line_start, line)
    return _open_item(view, line, line_start, before)


def _open_item(view: NoteView, line: str, line_start: int, before: int) -> tuple[int, int, str, bool | None] | None:
    """The list item `line` just made, as `_wrap_item` needs it; None when the line made none."""
    item = _ITEM.match(line)
    if not item or len(view.sentences) != before + 1 or view.sentences[-1].kind not in ("item", "task"):
        return None
    return before, line_start + item.end(), view.sentences[-1].kind, view.sentences[-1].done


#: A title that says something ("Uni is done!!") rather than names the note.
_SAYS = lazy_compile(r"\b(?:is|are|was|were|am|has|have|had)\b|[!?]\s*$", re.I)
#: A body that leans on a word the title gives ("... but it's done").
_LEANS = lazy_compile(r"\b(?:it|that|this)(?:'s|\u2019s| is| was)\b", re.I)


def title_is_content(title: str, body: str) -> bool:
    """Whether a note's title is part of what it says (INBOX 1665 g: "Uni is
    done!!" over "... but it's done haha!"): the title says something, and
    the body leans on "it" or "that" and never says the title's subject."""
    if not title or not _SAYS.search(title) or not _LEANS.search(body):
        return False
    subject = next(iter(_words(title)), None)
    return subject is not None and subject not in set(_words(body))


def _title_unit(view: NoteView, content: str, line_start: int, line: str) -> None:
    """The title line, read as the first sentence of the note."""
    lead = _HEADING_LEAD.match(line)
    start = line_start + (lead.end() if lead else 0)
    raw = line[(lead.end() if lead else 0):].rstrip("\r\n")
    raw = composer_frame.strip_end_emoticon(raw)
    unit = _unit(view, content, start, start + len(raw), "prose", None)
    if unit:
        view.sentences.append(unit)


def _read_title(view: NoteView, content: str, front: int, body_start: int, title: str) -> None:
    """The title line is a sentence of its own when it says the note's point."""
    if view.titled and view.kind == "note" and title_is_content(title, content[body_start:]):
        lines = content[front:].splitlines(keepends=True)
        if lines:
            _title_unit(view, content, front, lines[0])


#: Reads kept between answers (F8, L-chat-157): an answer parsed every one of the route's 400 notes, 40 ms of
#: 100 to 150. A read is kept by what it was made from, so an edit parses that note again and no other.
READ_CACHE_MAX = 600
_READ_CACHE_CHARS = 20_000
_reads: OrderedDict[tuple, NoteView] = OrderedDict()


def forget_reads() -> None:
    _reads.clear()


def cached_reads() -> int:
    return len(_reads)


def _copy_view(view: NoteView, note: dict, rank: int) -> NoteView:
    """A view of its own: a question scores and echoes sentences in place, so none may be shared."""
    sentences = [replace(s, rank=rank, words=list(s.words), echoes=list(s.echoes)) for s in view.sentences]
    return replace(view, note=note, rank=rank, sentences=sentences, words=set(view.words),
                   title_words=set(view.title_words), filed_words=set(view.filed_words))


def read_note(note: dict, rank: int) -> NoteView | None:
    """`_read_note_fresh`, remembered by the note's id, words, tags, category and day."""
    content = str(note.get("content") or "")
    if len(content) > _READ_CACHE_CHARS or note.get("id") is None:
        return _read_note_fresh(note, rank)
    key = (note["id"], hashlib.blake2b(content.encode("utf-8", "replace"), digest_size=16).digest(),
           tuple(str(t) for t in (note.get("tags") or [])), str(note.get("category") or ""),
           str(note.get("created_at") or ""), str(note.get("written") or ""), str(note.get("kind") or ""))
    kept = _reads.get(key)
    if kept is not None:
        _reads.move_to_end(key)
        return _copy_view(kept, note, rank)
    view = _read_note_fresh(note, rank)
    if view is not None:
        _reads[key] = _copy_view(view, {"id": note["id"]}, rank)
        while len(_reads) > READ_CACHE_MAX:
            _reads.popitem(last=False)
    return view


def _read_note_fresh(note: dict, rank: int) -> NoteView | None:
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
    item_open: tuple[int, int, str, bool | None] | None = None
    offset = 0
    _read_title(view, content, front, body_start, title)
    lines = content.splitlines(keepends=True)
    for at, line in enumerate(lines):
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
        if _skipped(view, content, lines, at, line_start, in_fence):
            item_open = None
            continue
        item_open = _read_line(view, content, line_start, line, item_open)
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
        #: A plain "- " line under a to-do title is a task not yet done (bt-compcomp-1109 item 9).
        todo = not box and realise.todo_titled(view.title)
        unit = _unit(
            view, content, line_start + item.end(), line_end,
            "task" if box or todo else "item",
            False if todo else None if not box else box.strip("[] \t").lower() == "x",
        )
        if unit:
            unit.depth = _depth(line)
            view.sentences.append(unit)
        return
    body = line_start + (len(line) - len(line.lstrip(" >")))
    cursor = body
    for match in _SPLIT.finditer(content, body, line_end):
        stop = match.end(1) if match.group(1) else match.end(2) if match.group(2) else match.end(3)
        unit = _unit(view, content, cursor, stop, "prose", None)
        if unit:
            view.sentences.append(unit)
        cursor = match.end()
    unit = _unit(view, content, cursor, line_end, "prose", None)
    if unit:
        view.sentences.append(unit)


# --- scoring --------------------------------------------------------------------

_NUMBER_CUE = lazy_compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
    r"hundred|thousand|dozen|half|twice|double)\b",
    re.I,
)


_CAUSE_CUE = lazy_compile(r"\b(because|since|so that|which is why|that is why|due to|caused|the reason|means)\b", re.I)


_WHERE_CUE = lazy_compile(
    r"\b(?:in|at|near|on|by|from|to) (?:the )?[A-Z][\w-]+|\b(street|road|avenue|address|room|floor|hotel|station|"
    r"shop|office|cafe|restaurant|square|park|airport|flat|house|apartment|upstairs|downstairs|drawer|shelf|garage)\b",
)


_WHO_CUE = lazy_compile(r"\b(people|person|someone|team|testers?|users?|he|she|they|asked|said)\b", re.I)


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
