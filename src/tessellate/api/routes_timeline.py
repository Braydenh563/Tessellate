"""The notebook on a time axis (roadmap §10B).

Asked for repeatedly, and with more shape each time: *"I want a note timeline
where I can see notes visually by what time they were made. Maybe I can even
group them by events or related places etc."* The axis is time; the **bands**
are what makes it a map of what happened rather than a sorted list.

Two decisions worth knowing:

**A note can appear at a date it was not written on.** §10A resolved the
relative time in note text, "the deadline is next Friday" knows which Friday
- so a note plots at what it is *about* when it says something, and at when it
was written otherwise. That is the whole reason the timeline is more than
`ORDER BY created_at`, and every placed note says which of the two it used so
the view can be honest about it.

**Bands come from what is already stored**, category, tag, or a note thread
(`Entry.parent_id`, §87.6): rather than from an `events` table that does not
exist yet. Grouping by event is still the goal (§10), and this is the shape
it will slot into: one more `group` value.
"""

from __future__ import annotations

import base64
import binascii
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, String, and_, func, or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Document, Entry, EntryDate, EntryProperty, Reminder, Space, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import manager
from tessellate.entry import properties as note_properties

router = APIRouter(prefix="/timeline", tags=["timeline"])

# How the axis is bucketed. Anything longer than a year in days would be a
# scatter of one-note columns; anything shorter than a day is not a thing a
# notebook has enough of.
SCALES = {"day": 1, "week": 7, "month": 30, "year": 365}

# One band per category or tag, plus "everything else", a chart with forty
# lanes is not a chart. The cut-off is by note count, so the bands are the
# ones the user actually writes in.
MAX_BANDS = 8
OTHER_BAND = "Everything else"

#: A row's title is the first line of this, and the row's own CSS ellipsis is
#: what should cut it, at the row's edge. At 120 the cut came first: at 1440 a
#: 1248px title ended "...borrows as loans. #learn…" at x=896, with 430px of
#: empty row before the time (INBOX 464). 240 fills the widest row; the grid
#: and the band cards clamp their own lines.
PREVIEW_CHARS = 240

#: How many rows one request draws, and the ceiling on asking for more.
#:
#: **This replaced `MAX_NOTES = 1500`, a hard cap with no page after it**
#: (TIMELINE_PLAN decision 9). A notebook past the cap simply lost its older
#: notes off the end of the view, silently and with nothing on screen to say
#: so, because the old timeline was drawn rather than paged: a grid of bands
#: against buckets has no "next". A feed does, so the view asks for a page at a
#: time and fetches the next as the reader reaches the end of this one.
PAGE_SIZE = 300
MAX_PAGE = 1000


def _clip(text: str, limit: int = PREVIEW_CHARS) -> str:
    """A preview that says it's a preview. A bare `text[:limit]` slice: 
    what this used to be, cuts a note off mid-word with nothing to say so,
    which is the "no ellipsis" the grid view was reported for: the card
    genuinely had less text than the note, and nothing on screen said that.
    """
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _decode_cursor(cursor: str) -> str:
    return base64.urlsafe_b64decode(cursor.encode()).decode()


#: **What a timeline row can be** (TIMELINE_PLAN.md Phase 4, decision 9). A
#: notebook's day is not only its notes: a document written, a board drawn and
#: a reminder due are all "what was I doing then", and the feed said nothing
#: about any of them. Boards were always here and were always shaped like
#: notes (a board *is* an `Entry`, MINDMAP_PLAN.md §2); documents and reminders
#: are their own tables and join the feed here.
KINDS = ("note", "board", "document", "reminder")

#: Which table each kind is read from. Notes and boards share one, which is why
#: the cursor is per *source* rather than per kind: one query serves both.
_SOURCE_OF = {"note": "entry", "board": "entry", "document": "document", "reminder": "reminder"}
_SOURCES = ("entry", "document", "reminder")


def _requested_kinds(kind: str | None) -> tuple[str, ...]:
    """The kinds a caller asked for, or all of them.

    Comma separated rather than repeated (`kind=note&kind=board`) because it is
    what the dock's chips build and what a shared link carries; an unknown name
    is a 422 rather than a silent empty feed, which is the failure that reads as
    "the timeline is broken".
    """
    if not kind:
        return KINDS
    asked = tuple(part.strip() for part in kind.split(",") if part.strip())
    unknown = [name for name in asked if name not in KINDS]
    if unknown or not asked:
        raise HTTPException(
            status_code=422, detail=f"Pick one or more of: {', '.join(KINDS)}."
        )
    #: Deduplicated in the declared order, so `kind=board,note` and
    #: `kind=note,board` are the same request and cache the same way.
    return tuple(name for name in KINDS if name in asked)


def _encode_marks(marks: dict[str, tuple[datetime, int]]) -> str:
    """Where each source stopped, as one opaque string.

    **One cursor per source, not one cursor.** The feed is a merge of three
    tables ordered by three different columns, and a single `at|id` pair cannot
    say where a merge stopped: two rows from different tables can share a
    timestamp, and an id means nothing across tables. Each source continues
    from its own last returned row, which makes the next page exactly the rows
    that were left over, with no duplicate and no gap.
    """
    parts = [
        f"{source}:{at.isoformat()}|{row_id}"
        for source, (at, row_id) in sorted(marks.items())
    ]
    return base64.urlsafe_b64encode(";".join(parts).encode()).decode()


def _decode_marks(cursor: str) -> dict[str, tuple[datetime, int]]:
    """The inverse, and tolerant of the single-source cursor this endpoint
    issued before documents and reminders joined the feed: a reader who was
    half way down the page when the app updated keeps their place instead of
    getting a 422 on the next scroll.
    """
    marks: dict[str, tuple[datetime, int]] = {}
    for part in _decode_cursor(cursor).split(";"):
        if not part:
            continue
        head, _, rest = part.partition(":")
        #: An ISO timestamp is full of colons, so the prefix is only a source
        #: name when it actually is one.
        if head in _SOURCES and rest:
            source, body = head, rest
        else:
            source, body = "entry", part
        at_text, _, id_text = body.rpartition("|")
        marks[source] = (datetime.fromisoformat(at_text), int(id_text))
    return marks


def _older_than(column, id_column, mark: tuple[datetime, int] | None):
    """The "strictly after this row in the order" clause for one source."""
    if mark is None:
        return None
    at, row_id = mark
    return or_(column < at, and_(column == at, id_column < row_id))


def _bucket_start(when: datetime, scale: str) -> str:
    """The label of the bucket this moment belongs to."""
    if scale == "day":
        return when.date().isoformat()
    if scale == "week":
        return (when.date() - timedelta(days=when.weekday())).isoformat()
    if scale == "month":
        return when.date().replace(day=1).isoformat()
    return when.date().replace(month=1, day=1).isoformat()


def _place_notes(
    entries: list,
    placed: list[dict],
    scale: str,
    resolved: dict,
    categories: dict,
    spaces: dict,
    links: dict,
    meetings: dict | None = None,
    every: dict | None = None,
) -> None:
    """One feed row per note, placed by the date the note is *about*.

    A meeting (INBOX 644) is about its `date:` property, which beats any
    phrase in its text: "by Friday" in an action item is when something is
    due, not when the meeting was.

    Lifted out of `timeline` unchanged (WORLD_CLASS_PLAN A5): the route
    was 346 lines, of which the three row builders were 100. Everything
    this reads was batched into one query per column by the caller, which
    is why they arrive as dicts rather than as a session to ask again.
    """
    for entry in entries:
        meeting = (meetings or {}).get(entry.id)
        mention = meeting or resolved.get(entry.id)
        at = mention.at if mention else entry.created_at
        #: The property block is the note's metadata, not its words: a row
        #: titled "---" over "type: Meeting date: ..." was the preview of
        #: every note of a type (meetings-644 audit, item 5).
        text = note_properties.strip(manager.readable_content(entry)).lstrip("\n")
        #: **A mentioned day is a day, not an instant** (audit 2026-10-05,
        #: UX-02). `EntryDate.at` is the writer's own calendar day (and the
        #: clock they said with it, if any), with no zone. Served as
        #: `...T00:00:00+00:00` it was read as UTC midnight, which a browser
        #: west of UTC draws on the evening before: the dentist "on Friday"
        #: sat under Thursday 8:00 PM in New York. So a day row carries the
        #: date alone, and a row whose note said "at 3pm" carries that clock
        #: with no offset; the view groups and draws both as written.
        timed = bool(mention) and mention.precision == "minute"
        if mention:
            when = {
                "at": at.strftime("%Y-%m-%dT%H:%M:%S") if timed else at.date().isoformat(),
                "date": at.date().isoformat(),
                "time": at.strftime("%H:%M") if timed else None,
                "all_day": not timed,
            }
        else:
            when = {"at": at.isoformat()}
        placed.append(
            {
                "id": entry.id,
                #: **Identity across four kinds.** Note 3 and document 3 are
                #: two different things, and a view that keys its rows, its
                #: open state and its keyboard focus on the bare id would put
                #: one of them where the other should be. The id stays (it is
                #: what a row opens); this is what identifies the row.
                "kind": "board" if entry.is_board else "note",
                "key": f"{'board' if entry.is_board else 'note'}:{entry.id}",
                "_at": _naive(at),
                **when,
                "bucket": _bucket_start(at, scale),
                # Said out loud so the view can be honest: this note is here
                # because of what it talks about, not when it was typed.
                "placed_by": "meeting" if meeting else "mentioned" if mention else "written",
                #: The other days the note names (the row sits on one): the
                #: calendar draws an "also on" chip there (decision 23).
                "also_on": _also_on(every, entry.id, when),
                "phrase": mention.phrase if mention else "",
                "written_at": entry.created_at.isoformat(),
                "category": categories.get(entry.category_id, manager.UNCATEGORISED),
                "tags": manager.shown_tags(entry),
                # Only read by `_thread_bands` (group=thread): carried for
                # every note regardless of the chosen group so switching to
                # "Thread" never needs a second fetch.
                "parent_id": entry.parent_id,
                "pinned": entry.pinned,
                # The space's own name, not its id: the id is a slug nobody
                # named, and the column has to be readable. It falls back to
                # the id for a space that has been deleted out from under its
                # notes, which is more honest than an empty cell.
                "space": spaces.get(entry.workspace_id, entry.workspace_id),
                # A word count, not a character count: it is the number people
                # think in, and `_clip` has already thrown the characters away.
                "words": len(text.split()),
                "links": len(links.get(entry.id, [])),
                "preview": _clip(text),
            }
        )


def _also_on(every: dict | None, entry_id: int, when: dict) -> list[str]:
    """The days a note names besides the one it is placed on, in text order."""
    placed = when.get("date") or str(when.get("at", ""))[:10]
    seen: list[str] = []
    for day in (every or {}).get(entry_id, []):
        if day != placed and day not in seen:
            seen.append(day)
    return seen


class _MeetingAt:
    """A meeting's `date:` in the shape `_place_notes` reads a mention in."""

    __slots__ = ("at", "precision", "phrase")

    def __init__(self, at: datetime, timed: bool) -> None:
        self.at = at
        self.precision = "minute" if timed else "day"
        self.phrase = ""


def _meeting_dates(session: Session, entry_ids: list[int]) -> dict[int, _MeetingAt]:
    """Each meeting's own date, from the property index (two queries for
    the page): a note typed Meeting whose `date:` reads as one. The value is
    the writer's wall clock, as a mention's is (UX-02)."""
    if not entry_ids:
        return {}
    typed = set(
        session.scalars(
            select(EntryProperty.entry_id).where(
                EntryProperty.entry_id.in_(entry_ids),
                EntryProperty.key == "type",
                func.lower(EntryProperty.value) == "meeting",
            )
        )
    )
    if not typed:
        return {}
    found: dict[int, _MeetingAt] = {}
    for row in session.scalars(
        select(EntryProperty).where(
            EntryProperty.entry_id.in_(typed),
            EntryProperty.key == "date",
            EntryProperty.date.is_not(None),
        )
    ):
        found.setdefault(row.entry_id, _MeetingAt(row.date, len(row.value.strip()) > 10))
    return found


def _place_documents(documents_found: list, placed: list[dict], scale: str, spaces: dict) -> None:
    """One feed row per document, placed by when it was started.

    Lifted out of `timeline` unchanged (WORLD_CLASS_PLAN A5). Not by when
    it was last saved: a note plots where it was written, and a document
    that plotted at `updated_at` would walk forwards through the feed every
    time it was opened, which is the one thing a journal must not do.
    """
    placed.extend(
        {
            "id": document.id,
            "kind": "document",
            "key": f"document:{document.id}",
            "_at": _naive(document.created_at),
            "at": document.created_at.isoformat(),
            "bucket": _bucket_start(document.created_at, scale),
            "placed_by": "written",
            "phrase": "",
            "written_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "category": "",
            "tags": [],
            "parent_id": None,
            "pinned": False,
            "space": spaces.get(document.workspace_id, document.workspace_id),
            "words": len((document.content or "").split()),
            "links": 0,
            "preview": _clip(_first_line(document.content or "")),
            "title": document.title or "Untitled",
            "file_type": document.file_type,
        }
        for document in documents_found
    )



def _place_reminders(reminders_found: list, placed: list[dict], scale: str, spaces: dict) -> None:
    """One feed row per reminder, placed by the date it is due.

    Lifted out of `timeline` unchanged (WORLD_CLASS_PLAN A5).
    """
    placed.extend(
        {
            "id": reminder.id,
            "kind": "reminder",
            "key": f"reminder:{reminder.id}",
            "_at": _naive(reminder.due_at),
            "at": reminder.due_at.isoformat(),
            "bucket": _bucket_start(reminder.due_at, scale),
            #: The same word a note gets when it sits on a date it only
            #: talks about, because it is the same claim: this row is here
            #: for what it is about, not for when it was typed.
            "placed_by": "due",
            "phrase": "",
            "written_at": reminder.created_at.isoformat(),
            "category": "",
            "tags": [],
            "parent_id": None,
            "pinned": False,
            "space": spaces.get(reminder.workspace_id, reminder.workspace_id),
            "words": len((reminder.text or "").split()),
            "links": 0,
            "preview": _clip(reminder.text or ""),
            "title": reminder.text or "Reminder",
            "done": reminder.done,
            "priority": reminder.priority,
            "entry_id": reminder.entry_id,
        }
        for reminder in reminders_found
    )


@router.get("")
def timeline(
    # Days by default: a month bucket puts a whole month of notes in one
    # column, which is the shape the Timeline exists to break up.
    scale: str = "day",
    group: str = "category",
    # 0 means "everything" (see below) and is a real, used value, the lower
    # bound has to allow it. The upper bound exists because `timedelta(days=…)`
    # raises OverflowError past ~999999999 days, which an unvalidated `days`
    # let straight through as an unhandled 500 instead of a clean 422; ~110
    # years is generously past any real notebook's age.
    days: int = Query(default=365, ge=0, le=40000),
    start: str | None = None,
    end: str | None = None,
    #: One page of rows, and where the last one stopped. Both optional: a
    #: caller that asks for neither gets the first page, which is what every
    #: caller before paging existed was already getting.
    limit: int = PAGE_SIZE,
    cursor: str | None = None,
    #: Which kinds of thing the feed holds (TIMELINE_PLAN decision 9). Comma
    #: separated, omitted for all four.
    kind: str | None = None,
    #: "On this day" (TIMELINE_PLAN section 8): `MM-DD`, what was written on
    #: that calendar day in an earlier month or year, in the reader's own day
    #: (`tz`, minutes east of UTC), today itself left out. The Dashboard's On
    #: this day widget's rule, so the two never disagree.
    on: str | None = Query(default=None, pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"),
    tz: int = Query(default=0, ge=-840, le=840),
    #: The calendar's window also holds a note that names a date in it as a
    #: second or later date (its row stays on the first; `also_on` lists the
    #: rest), so the grid can show it there too (TIMELINE_PLAN decision 23).
    also: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    """The notebook on a time axis, in bands.

    `scale` buckets the axis (day/week/month/year), `group` chooses the bands
    (category/tag/thread/none), `days` is how far back to look, 0 for
    everything, `kind` is which of notes, boards, documents and reminders the
    feed holds.
    """
    kinds = _requested_kinds(kind)
    if scale not in SCALES:
        raise HTTPException(
            status_code=422, detail=f"Pick one of: {', '.join(SCALES)}."
        )
    if group not in ("category", "tag", "thread", "none"):
        raise HTTPException(
            status_code=422, detail="Pick one of: category, tag, thread, none."
        )

    if limit < 1 or limit > MAX_PAGE:
        raise HTTPException(status_code=422, detail=f"Ask for between 1 and {MAX_PAGE} items at a time.")

    query = select(Entry).where(
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_private == False,  # noqa: E712  # private text stays out of a view
    )
    #: A board is an `Entry` with `is_board` set, so "notes only" and "boards
    #: only" are one query with a flag rather than two code paths.
    if "note" in kinds and "board" not in kinds:
        query = query.where(Entry.is_board == False)  # noqa: E712
    elif "board" in kinds and "note" not in kinds:
        query = query.where(Entry.is_board == True)  # noqa: E712
    #: **The range, once, applied to each source's own column.** The three
    #: tables the feed reads are dated by three different columns, so a window
    #: expressed as an `Entry` clause cannot be reused: it is computed here and
    #: handed to each query.
    since: datetime | None = None
    until: datetime | None = None
    if start and end:
        try:
            since = datetime.fromisoformat(start)
            until = datetime.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=422, detail="Write the start and end as dates, like 2026-10-04.")
    elif days > 0:
        since = utcnow() - timedelta(days=days)

    shift = f"{tz:+d} minutes"
    today_here = (utcnow() + timedelta(minutes=tz)).date().isoformat()

    def in_range(statement: Select, column) -> Select:
        if since is not None:
            statement = statement.where(column >= since)
        if until is not None:
            statement = statement.where(column <= until)
        if on:
            #: The stored instant moved into the reader's day, then compared
            #: by month and day; today's own rows are not a memory.
            statement = statement.where(
                func.strftime("%m-%d", column, shift) == on,
                func.strftime("%Y-%m-%d", column, shift) != today_here,
            )
        return statement

    query = _ranged_entries(query, in_range, (start, end, on), since, until, tz, also)

    # The density strip is the whole range, however little of it this page
    # holds: it is the overview a reader drags to get somewhere, so a strip
    # drawn from one page would be a map of the part you can already see. Two
    # columns and no content, so it stays cheap as the notebook grows.
    density = (
        _density(session, query) if ("note" in kinds or "board" in kinds) else {}
    )

    #: **Where the last page stopped**, one mark per source rather than an
    #: offset: an offset shifts under a note saved while someone is reading,
    #: which shows a row twice or skips one, and a single mark cannot describe
    #: where a merge of three tables got to (see `_encode_marks`).
    marks: dict[str, tuple[datetime, int]] = {}
    if cursor:
        try:
            marks = _decode_marks(cursor)
        except (ValueError, binascii.Error, TypeError):
            raise HTTPException(status_code=422, detail="That page marker is not valid. Reload the timeline and try again.")

    def page_of(statement: Select, column, id_column, source: str) -> list:
        """One source's next `limit + 1` rows, oldest mark honoured.

        One more than the page, which is how the answer knows whether there is
        a page after this one without a second count query. Taking `limit + 1`
        from *each* source is also what makes the merge below correct: the
        newest `limit + 1` rows overall are always inside the union of the
        newest `limit + 1` of each.
        """
        clause = _older_than(column, id_column, marks.get(source))
        if clause is not None:
            statement = statement.where(clause)
        return list(
            session.scalars(statement.order_by(column.desc(), id_column.desc()).limit(limit + 1))
        )

    entries_found: list[Entry] = []
    if "note" in kinds or "board" in kinds:
        entries_found = page_of(query, Entry.created_at, Entry.id, "entry")

    documents_found: list[Document] = []
    if "document" in kinds:
        documents_found = page_of(
            #: An archived document is "kept, out of the way" (its own model
            #: says so), which is the one thing a journal of what you were
            #: doing should not put back in front of you.
            in_range(
                select(Document).where(Document.archived_at.is_(None)), Document.created_at
            ),
            Document.created_at,
            Document.id,
            "document",
        )

    reminders_found: list[Reminder] = []
    if "reminder" in kinds:
        #: Placed by `due_at`, not by when it was typed: a reminder is *about*
        #: the day it is due, which is the same claim a note makes when it
        #: mentions a date, and the row says so the same way (`placed_by`).
        reminders_found = page_of(
            in_range(select(Reminder), Reminder.due_at), Reminder.due_at, Reminder.id, "reminder"
        )

    #: The scrubber answers "how much was going on then", so it counts every
    #: kind the feed is showing rather than only the notes: a week spent
    #: writing one long document would otherwise read as an empty week.
    #: Date-only queries, no content, the same shape `_density` itself uses.
    if "document" in kinds:
        for (created,) in session.execute(
            in_range(
                select(Document.created_at).where(Document.archived_at.is_(None)),
                Document.created_at,
            )
        ).all():
            day = created.date().isoformat()
            density[day] = density.get(day, 0) + 1
    if "reminder" in kinds:
        for (due,) in session.execute(
            in_range(select(Reminder.due_at), Reminder.due_at)
        ).all():
            day = due.date().isoformat()
            density[day] = density.get(day, 0) + 1

    entries = entries_found

    # What each note is *about*, where it said so. One query rather than one
    # per note: a timeline over a year of notes would otherwise be hundreds.
    resolved: dict[int, EntryDate] = {}
    every: dict[int, list[str]] = {}
    if entries:
        rows = session.scalars(
            select(EntryDate)
            .where(EntryDate.entry_id.in_([entry.id for entry in entries]))
            .order_by(EntryDate.id)
        )
        for row in rows:
            resolved.setdefault(row.entry_id, row)
            every.setdefault(row.entry_id, []).append(row.at.date().isoformat())

    meetings = _meeting_dates(session, [entry.id for entry in entries])

    categories = manager.bulk_category_names(session, entries)

    # The table view's columns (TIMELINE_PLAN decision 6): which space a note
    # is in, how long it is and how many notes it is joined to. All three are
    # one query each for the whole page rather than one per row, the same
    # batching `resolved` above uses: a timeline over a year of writing is
    # hundreds of rows and this endpoint is drawn on every visit to the tab.
    spaces = {space.id: space.name for space in session.scalars(select(Space))}
    links = manager.links_for_entries_bulk(session, [entry.id for entry in entries])

    placed = []
    _place_notes(entries, placed, scale, resolved, categories, spaces, links, meetings, every)

    _place_documents(documents_found, placed, scale, spaces)
    _place_reminders(reminders_found, placed, scale, spaces)

    #: **The merge.** Three sources, each already in order, cut to one page
    #: here rather than in SQL: a UNION over three tables with three different
    #: date columns is a query no index helps and one nobody can read.
    placed.sort(key=lambda row: (row["_at"], row["id"]), reverse=True)
    more_in_a_source = (
        len(entries_found) > limit or len(documents_found) > limit or len(reminders_found) > limit
    )
    has_more = more_in_a_source or len(placed) > limit
    placed = placed[:limit]

    #: Each source continues from the oldest row of its own that made it into
    #: this page. A source with nothing in the page keeps the mark it came in
    #: with, so it is asked the same question again rather than skipped.
    next_marks = dict(marks)
    for row in placed:
        next_marks[_SOURCE_OF[row["kind"]]] = (row["_at"], row["id"])
    next_cursor = _encode_marks(next_marks) if has_more and next_marks else None
    for row in placed:
        row.pop("_at", None)

    return {
        "scale": scale,
        "group": group,
        "kinds": list(kinds),
        #: **The rows.** The key said `notes` from the days when the feed held
        #: only notes, and both keys carried the same list for the releases
        #: a cached build might still read `notes` (the plan was to drop it
        #: after 0.3.0). Dropped on 0.3.32 (audit 2026-10-05, ARCH-11): at
        #: 5,000 notes it was 175 KB of the 350 KB page, built and encoded
        #: twice, for a frontend that reads `rows` only.
        "rows": placed,
        #: Bands are a property of notes (a category, a tag, a thread), so they
        #: are counted over the rows that have those and not over the feed.
        "bands": _bands([row for row in placed if row["kind"] in ("note", "board")], group),
        "buckets": sorted({note["bucket"] for note in placed}),
        # Counts per day for the whole range, which the view aggregates to
        # whatever bucket it is drawing: the scale is the reader's choice and
        # can change without asking again.
        "density": density,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def _first_line(text: str) -> str:
    """The opening line of a document, as its one-line preview: its title is
    already the row's title, so repeating the heading under it would be the
    source-card duplication in another place."""
    for line in (text or "").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _naive(at: datetime) -> datetime:
    """A comparable moment. Rows from three tables are sorted together, and
    Python refuses to compare an aware datetime with a naive one: most rows
    here are naive UTC, and one saved with an offset would otherwise raise a
    500 on the merge rather than sort slightly oddly."""
    return at.astimezone(timezone.utc).replace(tzinfo=None) if at.tzinfo else at


def _first_mentioned():
    """A note's first mentioned date (lowest id), the one its row sits on."""
    return (
        select(EntryDate.at)
        .where(EntryDate.entry_id == Entry.id)
        .order_by(EntryDate.id)
        .limit(1)
        .correlate(Entry)
        .scalar_subquery()
    )


def _meeting_date():
    """A meeting's own `date:`, which beats any mention (`_meeting_dates`)."""
    typed = (
        select(EntryProperty.id)
        .where(
            EntryProperty.entry_id == Entry.id,
            EntryProperty.key == "type",
            func.lower(EntryProperty.value) == "meeting",
        )
        .correlate(Entry)
        .exists()
    )
    return (
        select(EntryProperty.date)
        .where(EntryProperty.entry_id == Entry.id, EntryProperty.key == "date", EntryProperty.date.is_not(None), typed)
        .order_by(EntryProperty.id)
        .limit(1)
        .correlate(Entry)
        .scalar_subquery()
    )


def _ranged_entries(query: Select, in_range, asked: tuple, since, until, tz: int, also: bool = False) -> Select:
    """The notes in range, by where they *sit*: a meeting's own date, else the
    date the note mentions, else when it was written. An explicit window
    (`start` and `end`) and the feed's "last N days" are the same rule, so a
    note about a day this month written years ago is in the feed and the
    calendar alike (TIMELINE_PLAN decision 24). "On this day" (`on`) is a
    question about when things were written, and keeps that meaning."""
    start, end, on = asked
    if on or (since is None and until is None):
        return in_range(query, Entry.created_at)
    return _entries_in_window(query, since, until, tz, also)


def _entries_in_window(query: Select, since: datetime | None, until: datetime | None, tz: int, also: bool = False) -> Select:
    """Notes that *sit* in a window (TIMELINE_PLAN section 9).

    A note is in it by the day its row is placed on: a meeting's own date, else
    the date it mentions, else when it was written. Measured on the calendar
    sweep: a day page written in March and titled for today was on the feed's
    today and missing from the calendar's. A mentioned date is the writer's
    wall clock with no zone, so it is compared with the window moved by `tz`.
    A window with one end open (the feed's "last year" has no end) is bounded
    on the other side only.

    `also`: a note that names a date in the window as a later date counts too
    (its row still sits on the first, so the feed never asks for this).
    """
    first = func.coalesce(_meeting_date(), _first_mentioned())
    wall = timedelta(minutes=tz)
    written = [Entry.created_at >= since] if since is not None else []
    written += [Entry.created_at <= until] if until is not None else []
    placed = [first >= since + wall] if since is not None else []
    placed += [first <= until + wall] if until is not None else []
    clauses = [and_(first.is_(None), *written), and_(first.is_not(None), *placed)]
    if also:
        named = [EntryDate.entry_id == Entry.id]
        named += [EntryDate.at >= since + wall] if since is not None else []
        named += [EntryDate.at <= until + wall] if until is not None else []
        clauses.append(select(EntryDate.id).where(*named).correlate(Entry).exists())
    return query.where(or_(*clauses))


def _density(session: Session, ranged: Select) -> dict[str, int]:
    """How much was written on each day of the range, whatever page is loaded.

    It resolves placement the same way the rows do, a note sits on the date it
    talks about where it has one, so the strip and the feed agree about where
    the busy weeks are. Two id-and-date queries with no content in them: this
    stays affordable at a size where fetching every row would not, which is the
    whole reason the view is paged.
    """
    #: Counted in SQL (audit 2026-10-05, ARCH-11): this read every note's id
    #: and date and then sent all 5,000 ids back as `IN (...)` parameters for
    #: the mentioned dates, 78 ms of a 179 ms page. A note's first mentioned
    #: date (lowest id, as before) is a correlated read served by the
    #: `entry_id` index; dates are stored as naive UTC text, so the day is its
    #: first ten characters, which is what `.date()` gave on the row.
    first_mentioned = _first_mentioned()
    day = func.substr(func.coalesce(first_mentioned, Entry.created_at), 1, 10, type_=String)
    rows = session.execute(
        ranged.with_only_columns(day.label("day"), func.count()).order_by(None).group_by("day")
    ).all()
    return {str(when): int(count) for when, count in rows if when}


def _bands(notes: list[dict], group: str) -> list[dict]:
    """The lanes, biggest first, with a lane for the long tail."""
    if group == "none":
        return [{"name": "All notes", "count": len(notes), "ids": [n["id"] for n in notes]}]
    if group == "thread":
        return _thread_bands(notes)

    members: dict[str, list[int]] = defaultdict(list)
    for note in notes:
        if group == "category":
            members[note["category"]].append(note["id"])
        else:
            for tag in note["tags"] or ["untagged"]:
                members[tag].append(note["id"])

    ranked = sorted(members.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    bands = [
        {"name": name, "count": len(ids), "ids": ids} for name, ids in ranked[:MAX_BANDS]
    ]
    tail = ranked[MAX_BANDS:]
    if tail:
        ids = sorted({note_id for _, group_ids in tail for note_id in group_ids})
        bands.append({"name": OTHER_BAND, "count": len(ids), "ids": ids})
    return bands


THREAD_BAND = "Single notes & smaller threads"


def _thread_bands(notes: list[dict]) -> list[dict]:
    """One lane per thread, a root note and everything that continues it
    (`Entry.parent_id`), the one grouping a grid genuinely cannot show at
    all: a conversation with itself, spread across days or months (§87.6: 
    IDEAS.md's "branching line with offshoots", joined with the thread
    structure `parent_id` already stores). A parent outside the currently
    loaded window (out of the date range, private, or deleted) makes its
    child a root of its own rather than a second query reaching further
    back: the same honest simplification the `days` filter already asks
    the rest of this view to accept.

    A note with no children is not a thread, so it does not get its own
    lane: every such note, plus any real thread beyond the lane cap,
    folds into one shared band, the same shape category/tag grouping
    already uses for its own long tail.
    """
    by_id = {note["id"]: note for note in notes}

    def root_of(note: dict) -> dict:
        seen = {note["id"]}
        current = note
        # A parent chain is at most as deep as the notebook has notes; this
        # caps the walk defensively rather than trusting that shape holds.
        for _ in range(200):
            parent = by_id.get(current.get("parent_id"))
            if parent is None or parent["id"] in seen:
                return current
            seen.add(parent["id"])
            current = parent
        return current

    members: dict[int, list[int]] = defaultdict(list)
    roots: dict[int, dict] = {}
    for note in notes:
        root = root_of(note)
        members[root["id"]].append(note["id"])
        roots[root["id"]] = root

    threads = sorted(
        (item for item in members.items() if len(item[1]) > 1),
        key=lambda pair: (-len(pair[1]), pair[0]),
    )
    bands = [
        {"name": _clip(roots[root_id]["preview"], 40) or f"Note #{root_id}", "count": len(ids), "ids": ids}
        for root_id, ids in threads[:MAX_BANDS]
    ]
    solo_ids = {i for root_id, ids in members.items() if len(ids) == 1 for i in ids}
    overflow_ids = {i for _, ids in threads[MAX_BANDS:] for i in ids}
    other = solo_ids | overflow_ids
    if other:
        bands.append({"name": THREAD_BAND, "count": len(other), "ids": sorted(other)})
    return bands
