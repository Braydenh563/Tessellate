"""Phrases as filters (CHAT_PLAN section 2, the graph, library and settings
row): "connected to Harbor", "untouched since June", "tagged work",
"pinned", "edited last week" typed into the graph's or the Library's search
become filters, and the rest of the words stay a search.

`read(text, now)` gives `{filters, rest}`; `resolve(session, filters, now)`
gives the notes they leave. Days and stretches of days are the recogniser's
(`recognise.span`, `recognise.days_since`, decision 46): this file names the
verbs ("connected to", "untouched since") and never a date word.
`tests/fixtures/composer/filters_1010.json` is the 40-phrase set, at 1.0.

Settings are searched by what they do: `SETTING_WORDS` (now `meaning.GROUPS`,
Brief 94) groups the words a person says for one thing ("dark", "night",
"theme"), served to every search box (`GET /read/words`), which matches a row
when any word of a group the query names is in it.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.ai import meaning, recognise

#: `read` folds whitespace to one space before these run, so they say " " and never
#: `\s+` (a lazy group before `\s+` is polynomial on a run of tabs; CodeQL).
_CONNECTED = re.compile(r"\b(?:connected|linked|links?|joined|related) (?:to|with) (?!nothing\b)(.+?)(?= (?:and|that|which|tagged|edited|created|untouched)\b|[,;]|$)", re.I)
_ORPHAN = re.compile(r"\b(?:connected to nothing|not connected(?: to anything)?|unlinked|no links|orphans?|on their own|with no links)\b", re.I)
_UNTOUCHED = re.compile(r"\b(?:untouched|not (?:touched|edited|changed|opened|updated|looked at)|unchanged|stale|forgotten|neglected) (since|for|in) (.+?)(?= (?:and|that|tagged|connected)\b|[,;]|$)", re.I)
_EDITED = re.compile(r"\b(?:edited|changed|updated|touched|modified)\s+(.+?)(?=\s+(?:and|that|tagged|connected)\b|[,;]|$)", re.I)
_CREATED = re.compile(r"\b(?:created|written|made|added|new)\s+(.+?)(?=\s+(?:and|that|tagged|connected)\b|[,;]|$)", re.I)
_TAG = re.compile(r"(?:\btagged\s+(?:with\s+)?|\bwith the tag\s+|\btag\s+|(?<![\w&])#)([A-Za-z][\w-]{0,40})", re.I)
_CATEGORY = re.compile(r"\b(?:filed (?:in|under)|in the category|category|in the folder|under)\s+([A-Za-z][\w -]{0,40}?)(?=\s+(?:and|that|tagged|connected|edited)\b|[,;]|$)", re.I)
_PINNED = re.compile(r"\b(?:pinned|starred|favourites?|favorites?)\b", re.I)
_HAS = (
    ("image", re.compile(r"\bwith (?:a )?(?:pictures?|images?|photos?|screenshots?)\b", re.I)),
    ("file", re.compile(r"\bwith (?:an? )?(?:attachments?|files?|pdfs?)\b", re.I)),
    ("reminder", re.compile(r"\bwith (?:a )?reminders?\b", re.I)),
    ("link", re.compile(r"\bwith (?:a )?(?:web )?(?:links?|urls?)\b", re.I)),
)
_KINDS = (("board", re.compile(r"\b(?:boards?|whiteboards?|mind ?maps?|maps)\b", re.I)),)
_MENTION = re.compile(r"\b(?:mentioning|mentions|naming|that mention) (.+?)(?= (?:and|that|tagged|connected|edited)\b|[,;]|$)", re.I)
_FILLER = re.compile(r"\b(?:show|me|all|the|notes?|ones|everything|anything|that|which|are|is|were|was|only|just|my|and|with|find|list)\b", re.I)


def _past_day(phrase: str, now: datetime) -> date | None:
    """The first day of a stretch said in the past ("june", "last week"), or
    the day a length back ("3 months" before now)."""
    today = now.date()
    found = recognise.span(phrase, today, "past")
    if found is not None:
        return found[0]
    days = recognise.days_since(f"{phrase} ago", now)
    return today - timedelta(days=days) if days is not None else None


def _window(phrase: str, now: datetime) -> tuple[date, date] | None:
    from tessellate.search import query

    understood = query.understand(phrase, now)
    if understood.since is None:
        return None
    return understood.since, understood.until or now.date()


class _Reading:
    """The filters read so far and the spans of the text they used, so a later
    pattern does not take words an earlier one already did."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.filters: list[dict] = []
        self.taken: list[tuple[int, int]] = []

    def free(self, found: re.Match) -> bool:
        return not any(found.start() < end and start < found.end() for start, end in self.taken)

    def take(self, found: re.Match, item: dict) -> None:
        self.filters.append({**item, "said": found.group(0).strip()})
        self.taken.append((found.start(), found.end()))


def _read_links(r: _Reading) -> None:
    if found := _ORPHAN.search(r.raw):
        r.take(found, {"kind": "orphan"})
    elif found := _CONNECTED.search(r.raw):
        name = re.sub(r"^(?:the|my|a|an)\s+", "", found.group(1).strip(" .\"'“”"), flags=re.I)
        r.take(found, {"kind": "connected", "name": name})


def _read_dates(r: _Reading, now: datetime) -> None:
    if found := _UNTOUCHED.search(r.raw):
        day = _past_day(found.group(2).strip(), now)
        if day is not None:
            r.take(found, {"kind": "untouched", "since": day.isoformat()})
    for pattern, kind in ((_EDITED, "edited"), (_CREATED, "created")):
        if (found := pattern.search(r.raw)) and r.free(found):
            span = _window(found.group(1), now)
            if span is not None:
                r.take(found, {"kind": kind, "start": span[0].isoformat(), "end": span[1].isoformat()})


def _read_labels(r: _Reading) -> None:
    for found in _TAG.finditer(r.raw):
        r.take(found, {"kind": "tag", "name": found.group(1).lower()})
    if found := _CATEGORY.search(r.raw):
        r.take(found, {"kind": "category", "name": found.group(1).strip()})
    if found := _PINNED.search(r.raw):
        r.take(found, {"kind": "pinned"})


def _read_contents(r: _Reading) -> None:
    for name, pattern in _HAS:
        if found := pattern.search(r.raw):
            r.take(found, {"kind": "has", "what": name})
    for name, pattern in _KINDS:
        if found := pattern.search(r.raw):
            r.take(found, {"kind": "type", "what": name})
    if found := _MENTION.search(r.raw):
        r.take(found, {"kind": "mention", "name": found.group(1).strip()})


def read(text: str, now: datetime) -> dict:
    """`{filters: [{kind, ...}], rest}`; no filter when nothing is read."""
    r = _Reading(re.sub(r"\s+", " ", str(text or "")).strip())
    _read_links(r)
    _read_dates(r, now)
    _read_labels(r)
    _read_contents(r)
    rest = r.raw
    for start, end in sorted(r.taken, reverse=True):
        rest = rest[:start] + " " + rest[end:]
    rest = re.sub(r"\s+", " ", _FILLER.sub(" ", rest)).strip(" ,;.") if r.filters else r.raw
    return {"filters": r.filters, "rest": rest}


def _midnight(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.min)


def _where_links(session: Session, query, item: dict):  # noqa: ANN001
    from tessellate.core.database import LIKE_ESCAPE, Entry, EntryLink, like_escape
    from tessellate.entry.manager import find_by_wiki_name

    links = session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all()
    if item["kind"] == "orphan":
        linked = {a for a, _ in links} | {b for _, b in links}
        return query.where(Entry.id.not_in(linked) if linked else True)
    hub = find_by_wiki_name(session, item["name"])
    if hub is None:
        like = f"%{like_escape(item['name'])}%"
        hub = session.scalars(select(Entry).where(Entry.is_deleted == False, Entry.content.ilike(like, escape=LIKE_ESCAPE))  # noqa: E712
                              .order_by(Entry.id).limit(1)).first()
    near = {b for a, b in links if hub and a == hub.id} | {a for a, b in links if hub and b == hub.id}
    return query.where(Entry.id.in_(near))


def _where_has(session: Session, query, item: dict):  # noqa: ANN001
    from tessellate.core.database import Entry, Reminder

    what = item["what"]
    if what == "image":
        return query.where(Entry.content.ilike("%![%](%"))
    if what == "file":
        return query.where(or_(Entry.content.ilike("%/media/%"), Entry.content.ilike("%.pdf%")))
    if what == "link":
        return query.where(Entry.content.ilike("%http%"))
    if what == "reminder":
        return query.where(Entry.id.in_(select(Reminder.entry_id).where(Reminder.entry_id.is_not(None))))
    return query


def _where_dated(session: Session, query, item: dict):  # noqa: ANN001
    from tessellate.core.database import Entry

    if item["kind"] == "untouched":
        return query.where(Entry.updated_at < _midnight(item["since"]))
    column = Entry.updated_at if item["kind"] == "edited" else Entry.created_at
    return query.where(column >= _midnight(item["start"]), column < _midnight(item["end"]) + timedelta(days=1))


def _where_labelled(session: Session, query, item: dict):  # noqa: ANN001
    from tessellate.core.database import LIKE_ESCAPE, Category, Entry, like_escape

    if item["kind"] == "tag":
        return query.where(Entry.tags.ilike(f'%"{like_escape(item["name"])}"%', escape=LIKE_ESCAPE))
    if item["kind"] == "category":
        return query.join(Category, Category.id == Entry.category_id).where(
            Category.name.ilike(like_escape(item["name"]), escape=LIKE_ESCAPE))
    return query.where(Entry.pinned == True)  # noqa: E712


def _where_content(session: Session, query, item: dict):  # noqa: ANN001
    from tessellate.core.database import LIKE_ESCAPE, Entry, like_escape

    if item["kind"] == "type":
        return query.where(Entry.is_board == True)  # noqa: E712
    return query.where(Entry.content.ilike(f"%{like_escape(item['name'])}%", escape=LIKE_ESCAPE))


#: One narrowing per filter kind, walked by `resolve`.
_RESOLVERS = {
    "connected": _where_links, "orphan": _where_links,
    "untouched": _where_dated, "edited": _where_dated, "created": _where_dated,
    "tag": _where_labelled, "category": _where_labelled, "pinned": _where_labelled,
    "type": _where_content, "mention": _where_content, "has": _where_has,
}


def resolve(session: Session, filters: list[dict], now: datetime) -> list[int]:
    """The notes every filter leaves, newest first (at most 2,000)."""
    from tessellate.core.database import Entry

    #: Private notes and boards stay out, as in the reading tools (`tools._common._visible`):
    #: a private note's tags are plaintext, so "tagged X" would otherwise name it.
    query = select(Entry.id).where(
        Entry.is_deleted == False, Entry.is_draft == False, Entry.is_private == False, Entry.is_board == False  # noqa: E712
    )
    for item in filters:
        narrow = _RESOLVERS.get(item["kind"])
        if narrow is not None:
            query = narrow(session, query, item)
    return list(session.scalars(query.order_by(Entry.id.desc()).limit(2000)))


#: Words a person says for one thing, each group searched as one: what a
#: setting does, not only what its label says. One table for every search box
#: now (Brief 94, `ai/meaning.py`); the names stay for their callers.
SETTING_WORDS = meaning.GROUPS
SETTING_FILLER = meaning.FILLER


def setting_words() -> list[list[str]]:
    return [list(group) for group in SETTING_WORDS]

