"""Link offers: where a document's text names another note or document (VC5).

A writer types "the quarterly roadmap" without brackets and the editor can
offer `[[Quarterly roadmap|the quarterly roadmap]]` instead. No model is
involved: every name a `[[link]]` can resolve to goes into the vendored
FlashText trie once, and the text is walked once (about 27 ms to load 5,000
titles and 2 ms to scan a long page, measured when the row was written).

**What keeps an offer from being noise.**

- The first mention of a name only. A page that says "the budget" nine times
  has one place worth linking, and nine underlines are nine decisions.
- A one-word name must be written as the name is, with its capital
  ("Tessellate", not "tessellate"). A note called "Work" or "Budget" would
  otherwise be offered on every sentence that uses the word.
- A name under four characters is never searched for (`MENTION_MIN_TITLE_CHARS`,
  the same bar the unlinked-mentions panel uses), and one with a square
  bracket cannot be written as a `[[link]]` at all.
- Never inside code, an existing link, a markdown link or an address, and not
  a name the text already links somewhere.
- A private note, a binned or archived document and the document being
  written are not names.

**The span is the words as written.** FlashText lowercases the text it
scans, so each hit is checked against the original characters before it is
believed; a lowercase fold that changed the text's length (a few Unicode
capitals do) therefore costs an offer, never a wrong offset.

**Tags are not offered.** The plan row also named tags, but a document has no
tags: `#word` in a document is plain text with nothing behind it, so an offer
would write a word that does nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import filetypes
from tessellate.core.database import Document, Entry
from tessellate.entry.manager import WIKI_LINK, wiki_target
from tessellate.entry.mentions import MENTION_MIN_TITLE_CHARS
from tessellate.entry.properties import strip as strip_properties
from tessellate.vendor.flashtext import KeywordProcessor

#: Offers returned for one text. A document that names twelve other pages
#: has made its connections; the rest are noise in a suggestions panel.
OFFERS_MAX = 12
#: The longest text scanned. Past this the editor is not asking about prose.
TEXT_MAX = 400_000
#: A name longer than this in words is a sentence, not a title, and would
#: never recur verbatim.
NAME_MAX_WORDS = 8
NAME_MAX_CHARS = 80
#: The opening of a note read for its name: a note's properties block can
#: come first, so the first line is not at byte zero.
_OPENING_CHARS = 2000

_HEADING_MARK = re.compile(r"^\s{0,3}#{1,6}\s+")
_BRACKET = re.compile(r"[\[\]|]")
#: Spans an offer must never land in. One pass, earliest alternative wins:
#: a fence swallows what a backtick inside it would have matched.
_BLOCKED = re.compile(
    r"(?ms)^[ \t]*(?P<fence>```|~~~).*?(?:^[ \t]*(?P=fence).*?$|\Z)"
    r"|`[^`\n]+`"
    r"|\[\[[^\[\]\n]{1,120}\]\]"
    r"|\[[^\]\n]*\]\([^)\n]*\)"
    r"|\b(?:https?://|ftp://|mailto:|www\.)\S+"
    r"|<\/?[A-Za-z][^>\n]*>"
)


@dataclass(frozen=True)
class _Name:
    name: str
    kind: str


@dataclass
class _Index:
    key: tuple
    processor: KeywordProcessor
    names: dict[str, list[_Name]]


_cache: dict[str, _Index | None] = {"index": None}


def _usable(name: str) -> bool:
    if len(name) < MENTION_MIN_TITLE_CHARS or len(name) > NAME_MAX_CHARS:
        return False
    if len(name.split()) > NAME_MAX_WORDS or _BRACKET.search(name):
        return False
    return True


def _opening_name(content: str | None) -> str:
    first = strip_properties(content or "").strip().split("\n", 1)[0]
    return _HEADING_MARK.sub("", first).strip()


def _version(session: Session) -> tuple:
    """What changes when a name does: a count, the newest edit and the newest
    id, for the two tables. A rename moves `updated_at`; a delete moves the
    count; so the trie is rebuilt only when the answer could differ."""
    docs = session.execute(
        select(func.count(Document.id), func.max(Document.updated_at), func.max(Document.id)).where(
            Document.deleted_at.is_(None), Document.archived_at.is_(None)
        )
    ).one()
    notes = session.execute(
        select(func.count(Entry.id), func.max(Entry.updated_at), func.max(Entry.id)).where(
            Entry.is_deleted.is_(False), Entry.is_private.is_(False)
        )
    ).one()
    return (tuple(docs), tuple(notes))


def _collect(session: Session) -> dict[str, list[_Name]]:
    names: dict[str, list[_Name]] = {}

    def add(raw: str, kind: str) -> None:
        name = raw.strip()
        if _usable(name):
            names.setdefault(name.lower(), []).append(_Name(name, kind))

    for title, file_type in session.execute(
        select(Document.title, Document.file_type)
        .where(Document.deleted_at.is_(None), Document.archived_at.is_(None))
        .order_by(Document.id)
    ):
        if filetypes.get(file_type).previewable:
            add(title or "", "document")
    for (content,) in session.execute(
        select(func.substr(Entry.content, 1, _OPENING_CHARS))
        .where(Entry.is_deleted.is_(False), Entry.is_private.is_(False))
        .order_by(Entry.id)
    ):
        add(_opening_name(content), "note")
    return names


def _index(session: Session) -> _Index:
    key = _version(session)
    held = _cache["index"]
    if held is not None and held.key == key:
        return held
    names = _collect(session)
    processor = KeywordProcessor(case_sensitive=False)
    for lowered in names:
        processor.add_keyword(lowered, lowered)
    built = _Index(key, processor, names)
    _cache["index"] = built
    return built


def _blocked_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in _BLOCKED.finditer(text)]


def _inside(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(a < end and start < b for a, b in spans)


def _already_linked(text: str) -> set[str]:
    return {wiki_target(match.group(1)).lower() for match in WIKI_LINK.finditer(text)}


def _choose(options: list[_Name], written: str) -> _Name | None:
    """The name a hit means: a document wins over a note of the same name (a
    link written in a document opens the document first), and a one-word name
    only counts when it is written with its own capital."""
    best = options[0]
    for option in options:
        if option.kind == "document":
            best = option
            break
    if " " not in best.name and written != best.name:
        return None
    if " " not in best.name and not best.name[:1].isupper():
        return None
    return best


def _link(name: str, written: str) -> str:
    return f"[[{name}]]" if written == name else f"[[{name}|{written}]]"


def offers(session: Session, text: str, *, exclude_title: str | None = None) -> list[dict]:
    """The first mention of each known name in `text`, in text order."""
    if not text or not text.strip():
        return []
    text = text[:TEXT_MAX]
    index = _index(session)
    if not index.names:
        return []
    blocked = _blocked_spans(text)
    linked = _already_linked(text)
    skipped = (exclude_title or "").strip().lower()
    seen: set[str] = set()
    found: list[dict] = []
    for lowered, start, end in index.processor.extract_keywords(text, span_info=True):
        written = text[start:end]
        if written.lower() != lowered:
            continue
        if lowered in seen or lowered in linked or lowered == skipped or _inside(blocked, start, end):
            continue
        chosen = _choose(index.names[lowered], written)
        if chosen is None:
            continue
        seen.add(lowered)
        found.append(
            {"start": start, "end": end, "text": written, "kind": chosen.kind, "name": chosen.name, "link": _link(chosen.name, written)}
        )
        if len(found) >= OFFERS_MAX:
            break
    return found
