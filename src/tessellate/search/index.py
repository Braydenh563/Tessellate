"""One index over every kind (WORLD_CLASS_PLAN B3, SESSION_BRIEFS Brief 11).

Before this, the notebook had one index and five blind spots. `entries_fts`
covers notes, and covers them well (bm25, a porter stemmer, a spelling
vocabulary); a document, a file's extracted text, a bookmark and a reminder
were each found, when they were found at all, by a `LIKE` in whichever route
happened to want them. Searching for a word you know you wrote and getting
nothing because you wrote it in a document rather than a note is the same
failure as having no search at all, and it is the one people report.

So: a second FTS5 table, `search_index`, holding one row per indexed thing,
with the `kind` on the row. The engine (`search/engine.py`) reads it; this
module is the only thing that writes it.

**Why a second table rather than a `kind` column on `entries_fts`**, which is
what Brief 11 first proposed: `entries_fts` is an *external content* table
(`content='entries', content_rowid='id'`), so its rowids are `entries.id` and
its text is read back out of `entries`. Neither can hold a document: document
7 and note 7 would be the same row, and FTS5 would look for a document's text
in the notes table. The `kind` column arrives, as asked, but on a table that
can carry every kind. `entries_fts` stays exactly as it is, still serving
`keyword_search` and still backing the spelling vocabulary; nothing that works
today is rebuilt (CLAUDE.md §1).

**Why the write path hangs off the ORM flush rather than the event log**, which
is Brief 11's other first proposal, revised here with its measurement (the
revision is written into WORLD_CLASS_PLAN's "Decisions made"): the event log
does not see every write. `routes_documents.py` records `created`, `deleted`,
`archived` and `restored`, and records nothing when a document's text is
*edited*, which is the one write a search index most needs to hear about. An
index fed by events would have gone stale on the app's most common document
operation and looked, from the outside, exactly like search being broken. The
SQLAlchemy `after_flush` hook below sees every write to the six mapped classes
regardless of which route, job or script made it, which is the property Brief
7's decorator-plus-driver gave the event log: **a new call site cannot
silently miss out**. The driver shape is kept too: `source_for()` raises on an
unregistered name rather than quietly indexing nothing, so a seventh kind
added to `KINDS` fails `tests/test_search_engine.py` on the spot.

What this deliberately does not do: rebuild on a schedule, or index whiteboard
sketches, images and cards as rows of their own (a board's cards are notes,
and are indexed as notes). The *words* written on a board or a map (its text
boxes and its topics) are indexed, as part of that board's own row: a mind
map's whole content is its topics, and a map indexed by its `# Title` line
alone could not be found by anything written on it.
A full rebuild on a large notebook belongs to the job runtime (Brief 9), not
to a request; `rebuild()` is here for the one caller that needs it, a database
that has never had this table.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import event, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, object_session

from tessellate.entry.properties import strip as strip_properties

logger = logging.getLogger("tessellate.search.index")

#: The kinds the engine can return, and the kinds `kind:` accepts. The spec
#: (`tests/test_search_engine_spec.py`) names the first six; `map` came after
#: it. Reported: "Mind maps don't show in the Find anything universal search".
#: A map is a board whose `board_settings` says `type: "map"` (MINDMAP_PLAN
#: §4), and indexing it as a `board` meant the finder could only ever call it
#: one; a previous pass relabelled the board chip "boards & maps" instead of
#: telling the two apart, which the data always could.
#: `chat` came with the search box (decision 46): a saved chat and an Ask
#: turn are both something the person wrote and read, and "where did I ask
#: about that" was the one question the box could not answer.
#: `recording` came with the audio set (ledger libr-1011 row 1218): a kept
#: take is found by its title and by what was said in it.
KINDS = ("note", "document", "board", "map", "file", "bookmark", "reminder", "chat", "recording")

#: The kinds whose `ref_id` is an `entries.id`: the ones the embedding matrix
#: and the link graph know, so the only ones cosine and graph distance can
#: score. One name for it, because the engine asked "note or board" in five
#: places and a sixth that forgot the map would score maps at zero silently.
ENTRY_KINDS = ("note", "board", "map")

#: The whiteboard object kinds whose `data.content` is words someone wrote:
#: a board's text box and a map's topic. Images carry a url and reference
#: nodes carry an id of something indexed in its own right.
_WORDED_OBJECT_KINDS = ("text", "topic")

#: The FTS5 table's columns, in order. The first three are indexed (they are
#: what a query matches against); the rest are UNINDEXED, which in FTS5 means
#: "stored and readable, but not searchable": they are filters and payload, and
#: indexing them would let a note about "the file" match `has:file`.
_COLUMNS = (
    "title",
    "body",
    "tags",
    "kind",
    "ref_id",
    "source",
    "space",
    "flags",
    "written",
)

#: bm25 weights for the indexed columns, in column order. A title match is
#: worth four body matches and a tag match two: the same shape, and for the
#: same reason, as `entries_fts`'s own `bm25(entries_fts, 1.0, 4.0)`, where the
#: tag column is weighted over content.
BM25_WEIGHTS = (4.0, 1.0, 2.0)

#: How rowids are shared out between sources. A regular FTS5 table can delete
#: by rowid in O(1) and can only delete by anything else with a full scan, so
#: every row's identity has to *be* its rowid: `slot * SLOT_STRIDE + ref_id`.
#: A stride of a trillion leaves room for a trillion rows per source, which is
#: eleven orders of magnitude more than a personal notebook will ever hold, and
#: keeps the arithmetic readable in a debugger.
SLOT_STRIDE = 1_000_000_000_000


@dataclass(frozen=True)
class Row:
    """One indexable thing, as the index wants it."""

    title: str
    body: str
    tags: str = ""
    space: str = "default"
    #: Space-separated words that `is:` and `has:` can ask about, e.g.
    #: `pinned`, `archived`, `done`. Only what the row itself knows: whether a
    #: note has an attachment is a different table's business and is answered
    #: by the engine over the candidates, not by a join on every save.
    flags: str = ""
    #: ISO date, for `before:`/`after:` without parsing text at query time.
    written: str = ""


@dataclass(frozen=True)
class Source:
    """Where one kind's rows come from.

    `read` is the incremental path (one object that just changed, already in
    memory, so no query); `scan` is the rebuild path. `slot` is permanent: it
    is baked into every rowid this source has ever written, so changing one
    orphans that source's rows. New sources take the next free number.
    """

    name: str
    kind: str
    slot: int
    model: type
    read: Callable[[object], Row | None]
    scan: Callable[[Session], Iterable[tuple[int, Row]]]


_SOURCES: dict[str, Source] = {}
_BY_MODEL: dict[type, list[Source]] = {}


class UnknownSource(KeyError):
    """Asked for a source that was never registered. See `source_for`."""


def register(source: Source) -> Source:
    """Add a source. Called once per kind at import time, below."""
    if source.name in _SOURCES:
        raise ValueError(f"search index source {source.name!r} is registered twice")
    for existing in _SOURCES.values():
        if existing.slot == source.slot:
            raise ValueError(
                f"search index source {source.name!r} reuses slot {source.slot}, "
                f"which belongs to {existing.name!r}: slots are permanent"
            )
    if source.kind not in KINDS:
        raise ValueError(f"search index source {source.name!r} has kind {source.kind!r}, not in KINDS")
    _SOURCES[source.name] = source
    _BY_MODEL.setdefault(source.model, []).append(source)
    return source


def source_for(name: str) -> Source:
    """The source called `name`, or a loud failure.

    The driver shape from `core/events.py`: the point is the day someone adds
    a kind and no source with it. `tests/test_search_engine.py` walks `KINDS`
    through here, so the omission fails the build with a message saying what
    to write, instead of that kind silently never being findable.
    """
    try:
        return _SOURCES[name]
    except KeyError:
        raise UnknownSource(
            f"no search index source named {name!r}: register one in "
            f"src/tessellate/search/index.py (see the note source for the shape)"
        ) from None


def sources() -> tuple[Source, ...]:
    return tuple(_SOURCES.values())


def sources_for_kind(kind: str) -> tuple[Source, ...]:
    return tuple(s for s in _SOURCES.values() if s.kind == kind)


# --- the table ----------------------------------------------------------------


def ensure_table(connection) -> bool:  # noqa: ANN001  # a SQLAlchemy Connection
    """Create `search_index` if it is missing. Returns True when it was made.

    Called from `DatabaseManager.__init__` beside `_ensure_fts5`, the same
    additive convention every other schema change here follows.
    """
    existed = connection.exec_driver_sql(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='search_index'"
    ).scalar()
    if existed:
        return False
    columns = ", ".join(
        column if column in ("title", "body", "tags") else f"{column} UNINDEXED"
        for column in _COLUMNS
    )
    connection.exec_driver_sql(
        f"CREATE VIRTUAL TABLE search_index USING fts5({columns}, tokenize='porter unicode61')"
    )
    return True


def _rowid(source: Source, ref_id: int) -> int:
    return source.slot * SLOT_STRIDE + int(ref_id)


def _write(connection, source: Source, ref_id: int, row: Row | None) -> None:  # noqa: ANN001
    """Replace one row, or remove it when there is nothing to index.

    Delete-then-insert rather than an UPDATE: FTS5 updates are a delete and an
    insert anyway, and one shape covers "changed", "arrived" and "became
    private" without branching.
    """
    rowid = _rowid(source, ref_id)
    connection.exec_driver_sql("DELETE FROM search_index WHERE rowid = ?", (rowid,))
    if row is None:
        return
    connection.exec_driver_sql(
        f"INSERT INTO search_index(rowid, {', '.join(_COLUMNS)}) "
        f"VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})",
        (
            rowid,
            row.title,
            row.body,
            row.tags,
            source.kind,
            int(ref_id),
            source.name,
            row.space,
            row.flags,
            row.written,
        ),
    )


# --- the write path -----------------------------------------------------------


def _table_missing(session: Session) -> bool:
    """True when this database has no `search_index` yet.

    Cached per session: a test that builds a bare `Base.metadata` database
    without `DatabaseManager` has no such table, and a failed write on every
    flush would be both noisy and slow.
    """
    known = session.info.get("memorymap_index_table")
    if known is None:
        known = bool(
            session.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='search_index'")
            ).scalar()
        )
        session.info["memorymap_index_table"] = known
    return not known


@event.listens_for(Session, "after_flush")
def _index_on_flush(session: Session, flush_context) -> None:  # noqa: ANN001
    """Keep the index in step with whatever just changed, in the same
    transaction, from the objects already in memory.

    `after_flush` is the one place that knows the whole of a write: what was
    added, what was changed and what was deleted, with every value final and
    every id assigned. Raw SQL through `session.connection()` rather than the
    ORM: this runs *inside* a flush, so anything that touches the unit of work
    would re-enter it.

    An indexing failure is logged and swallowed. That is a guard, not a
    shrug: the alternative is a note that will not save because its index row
    would not write, and a notebook that refuses to record a thought is worse
    in every way than one whose search is briefly behind. `rebuild()` puts it
    right, and the log line says which row.
    """
    if not (session.new or session.dirty or session.deleted):
        return
    if _table_missing(session):
        return
    work: list[tuple[Source, int, Row | None]] = []
    for obj in list(session.deleted):
        for source in _BY_MODEL.get(type(obj), ()):
            ref_id = getattr(obj, "id", None)
            if ref_id is not None:
                work.append((source, ref_id, None))
    for obj in [*session.new, *session.dirty]:
        for source in _BY_MODEL.get(type(obj), ()):
            ref_id = getattr(obj, "id", None)
            if ref_id is None:
                continue
            try:
                work.append((source, ref_id, source.read(obj)))
            except Exception:  # noqa: BLE001  # see the docstring
                logger.warning("could not index %s %s", source.name, ref_id, exc_info=True)
    work.extend(_boards_touched_by_objects(session, {(s.name, ref) for s, ref, _ in work}))
    if not work:
        return
    connection = session.connection()
    for source, ref_id, row in work:
        try:
            _write(connection, source, ref_id, row)
        except Exception:  # noqa: BLE001  # see the docstring
            logger.warning("could not write index row for %s %s", source.name, ref_id, exc_info=True)


def _boards_touched_by_objects(
    session: Session, done: set[tuple[str, int]]
) -> list[tuple[Source, int, Row | None]]:
    """The board and map rows a whiteboard object's write changed.

    A topic is not a row of its own; its words are part of its board's row
    (`_board_words`), so adding, editing or deleting one has to re-read that
    board. A dirty object whose `data` and `board_id` did not change (a node
    dragged, a colour picked) says nothing new and is skipped: a drag saves
    on every drop, and each would otherwise rewrite the board's row for
    nothing. `done` is what the entry pass already wrote this flush.
    """
    from tessellate.core.database import Entry, WhiteboardObject

    board_ids: set[int] = set()
    for obj in [*session.new, *session.deleted]:
        if isinstance(obj, WhiteboardObject) and obj.board_id is not None:
            board_ids.add(int(obj.board_id))
    for obj in session.dirty:
        if not isinstance(obj, WhiteboardObject):
            continue
        state = sa_inspect(obj)
        moved = state.attrs.board_id.history
        if not (state.attrs.data.history.has_changes() or moved.has_changes()):
            continue
        for board_id in [*(moved.deleted or ()), obj.board_id]:
            if board_id is not None:
                board_ids.add(int(board_id))
    if not board_ids:
        return []
    out: list[tuple[Source, int, Row | None]] = []
    with session.no_autoflush:
        for board_id in sorted(board_ids):
            entry = session.get(Entry, board_id)
            if entry is None:
                continue
            for source in _BY_MODEL.get(Entry, ()):
                if (source.name, board_id) in done:
                    continue
                try:
                    out.append((source, board_id, source.read(entry)))
                except Exception:  # noqa: BLE001  # see `_index_on_flush`
                    logger.warning("could not index %s %s", source.name, board_id, exc_info=True)
    return out


def reconcile_boards(session: Session) -> bool:
    """Bring the board and map rows in line with what they should say.

    Returns True when anything was written. Run at every startup after the
    table exists, because two changes to what a board's row holds arrived
    after notebooks had already been indexed: maps got a kind (and a slot)
    of their own, and a board's row gained the words on it. Neither can be
    put right by the write path, which only sees what changes from now on.

    A diff, not a rebuild: boards are a handful of rows, so reading them all
    is cheap, and writing only the rows that differ keeps the second and
    every later startup a read-only no-op.
    """
    if _table_missing(session):
        return False
    connection = session.connection()
    changed = False
    for name in ("boards", "maps"):
        source = _SOURCES[name]
        low, high = source.slot * SLOT_STRIDE, (source.slot + 1) * SLOT_STRIDE
        existing = {
            int(ref_id): (title, body, tags, space, flags, written)
            for ref_id, title, body, tags, space, flags, written in connection.exec_driver_sql(
                "SELECT ref_id, title, body, tags, space, flags, written FROM search_index "
                "WHERE rowid >= ? AND rowid < ?",
                (low, high),
            ).all()
        }
        wanted = dict(source.scan(session))
        for ref_id, row in wanted.items():
            shape = (row.title, row.body, row.tags, row.space, row.flags, row.written)
            if existing.get(ref_id) != shape:
                _write(connection, source, ref_id, row)
                changed = True
        for ref_id in existing.keys() - wanted.keys():
            _write(connection, source, ref_id, None)
            changed = True
    return changed


def touch(session: Session, source_name: str, ref_id: int) -> None:
    """Re-index one thing by hand.

    For the writes the ORM cannot see: a bulk `UPDATE`, a raw migration, a
    file whose OCR text was filled in by a job that wrote it with
    `session.execute`. It re-reads the object rather than trusting a caller's
    copy.
    """
    if _table_missing(session):
        return
    source = source_for(source_name)
    obj = session.get(source.model, ref_id)
    row = source.read(obj) if obj is not None else None
    _write(session.connection(), source, ref_id, row)


def forget(session: Session, model: type, ids: Iterable[int]) -> int:
    """Take rows out for things a bulk statement is about to delete, or has.

    `touch` above re-reads one object; this is its bulk half, for the deletes
    that never reach the flush hook: emptying the bin (`manager._hard_delete`
    runs `DELETE FROM entries WHERE id IN (...)`) and deleting a space (every
    table in `routes_spaces.delete_space` goes by a query-level delete). Both
    left their rows here for good, measured: a purged note stayed findable
    with `is:deleted`, and a deleted space's notes, documents and reminders
    stayed findable from All spaces. Every source of the model is cleared,
    because a note and a board share `Entry` and the caller cannot know
    which of the two a row was indexed as. Returns rows removed.
    """
    wanted = [int(ref_id) for ref_id in ids]
    if not wanted or _table_missing(session):
        return 0
    rowids = [_rowid(source, ref_id) for source in _BY_MODEL.get(model, ()) for ref_id in wanted]
    removed = 0
    connection = session.connection()
    # In chunks: SQLite's default bound-parameter ceiling is 999 on older
    # builds, and a bin can hold more notes than that.
    for start in range(0, len(rowids), 500):
        chunk = rowids[start : start + 500]
        result = connection.exec_driver_sql(
            f"DELETE FROM search_index WHERE rowid IN ({', '.join('?' * len(chunk))})",
            tuple(chunk),
        )
        removed += max(result.rowcount or 0, 0)
    return removed


#: When the index was last rebuilt from scratch in this process, and with how
#: many rows per kind, for `/search/stats`. None until the first rebuild: a
#: notebook whose index has only ever been kept up by the flush hook has no
#: "last rebuilt" to report, and inventing one would say it was checked.
_last_rebuild: dict | None = None


def last_rebuild() -> dict | None:
    return dict(_last_rebuild) if _last_rebuild else None


def rebuild(session: Session, only: str | None = None) -> dict[str, int]:
    """Index everything from scratch. Returns rows written per kind.

    Two callers. A database that has never had the table (a notebook from
    before this existed): `DatabaseManager` runs it once at startup when
    `ensure_table` reports it created the table. And the re-index job
    (`model_manager._run_reindex`, behind Settings' "Rebuild search index"),
    which is the way to ask for one after a restore, an import or a bug; it
    was the one thing that could not be asked for (the `search-reindex-job`
    row). Never a request's own work: on a large notebook it is a job.
    """
    global _last_rebuild
    if _table_missing(session):
        return {}
    connection = session.connection()
    written: dict[str, int] = {kind: 0 for kind in KINDS}
    for source in _SOURCES.values():
        if only and source.name != only:
            continue
        connection.exec_driver_sql(
            "DELETE FROM search_index WHERE rowid >= ? AND rowid < ?",
            (source.slot * SLOT_STRIDE, (source.slot + 1) * SLOT_STRIDE),
        )
        for ref_id, row in source.scan(session):
            _write(connection, source, ref_id, row)
            written[source.kind] += 1
    if not only:
        _last_rebuild = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "rows": dict(written)}
    return written


def counts(session: Session) -> dict[str, int]:
    """How many rows the index holds per kind. Every kind is a key, at zero
    when nothing of that kind exists: "no bookmarks" and "bookmarks are not
    indexed" are different answers and a missing key renders them the same."""
    tally = {kind: 0 for kind in KINDS}
    if _table_missing(session):
        return tally
    rows = session.execute(text("SELECT kind, count(*) FROM search_index GROUP BY kind")).all()
    for kind, count in rows:
        if kind in tally:
            tally[kind] = int(count)
    return tally


# --- the sources --------------------------------------------------------------
#
# One per kind, registered at import. Each `read` takes an object that is
# already in memory and returns the row, or None for "this must not be in the
# index" (deleted, private, a board being read by the note source).


def _first_line(text_value: str | None, limit: int = 120) -> str:
    # A note opening with properties is named by what follows them (KG4); the
    # fence line itself ("---") was a result's title.
    for line in strip_properties(text_value or "").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:limit]
    return ""


def _tagstext(raw: str | None) -> str:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return ""
    return " ".join(str(tag) for tag in parsed) if isinstance(parsed, list) else ""


def _written(value: datetime | date | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _entry_kind(entry) -> str:  # noqa: ANN001
    """"note", "board" or "map" for one row of the entries table.

    The same read as `entry.manager.board_type_of`, repeated rather than
    imported for the reason this module imports nothing from above it: the
    index sits under the entry layer. Tolerant of every shape a JSON text
    column can hold: a bad value is an ordinary board, never an exception in
    the middle of a flush.
    """
    if not bool(getattr(entry, "is_board", False)):
        return "note"
    try:
        parsed = json.loads(getattr(entry, "board_settings", None) or "{}")
    except (TypeError, ValueError):
        return "board"
    if isinstance(parsed, dict) and parsed.get("type") == "map":
        return "map"
    return "board"


def _board_words(entry) -> str:  # noqa: ANN001
    """The words written on a board or a map: its text boxes and topics.

    Raw SQL on the entry's own session connection, not an ORM query: this
    runs inside `after_flush`, where anything touching the unit of work would
    re-enter it, and after the flush's SQL, so a topic added, edited or
    deleted in the same flush is already what the table says.
    """
    session = object_session(entry)
    board_id = getattr(entry, "id", None)
    if session is None or board_id is None or _table_missing(session):
        return ""
    placeholders = ", ".join("?" * len(_WORDED_OBJECT_KINDS))
    rows = session.connection().exec_driver_sql(
        f"SELECT data FROM whiteboard_objects WHERE board_id = ? AND kind IN ({placeholders}) "
        "ORDER BY id",
        (int(board_id), *_WORDED_OBJECT_KINDS),
    ).all()
    words = []
    for (raw,) in rows:
        try:
            data = json.loads(raw or "{}")
        except (TypeError, ValueError):
            continue
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, str) and content.strip():
            words.append(content.strip())
    return "\n".join(words)


def _entry_row(entry, *, want: str) -> Row | None:  # noqa: ANN001
    """A note, a board or a map, from the same table.

    A private note is never indexed, for the reason its ciphertext exists: an
    index of what an encrypted note says is the encryption undone. A binned or
    archived note *is* indexed, with a flag, so the bin stays searchable.
    """
    if entry is None or bool(getattr(entry, "is_private", False)):
        return None
    if _entry_kind(entry) != want:
        return None
    flags = []
    if getattr(entry, "pinned", False):
        flags.append("pinned")
    if getattr(entry, "is_deleted", False):
        flags.append("deleted")
    if getattr(entry, "archived_at", None):
        flags.append("archived")
    if getattr(entry, "is_draft", False):
        flags.append("draft")
    if getattr(entry, "source_url", None):
        flags.append("clipped")
    content = entry.content or ""
    body = content
    if want != "note":
        words = _board_words(entry)
        if words:
            body = f"{content}\n{words}" if content else words
    return Row(
        title=_first_line(content),
        body=body,
        tags=_tagstext(getattr(entry, "tags", "[]")),
        space=getattr(entry, "workspace_id", "default") or "default",
        flags=" ".join(flags),
        written=_written(getattr(entry, "created_at", None)),
    )


def _scan_entries(session: Session, *, want: str) -> Iterator[tuple[int, Row]]:
    from tessellate.core.database import Entry

    query = select(Entry).where(Entry.is_private == False)  # noqa: E712
    # Boards are a handful of rows in a notebook of thousands of notes, and
    # `reconcile_boards` scans them at every startup, so that scan must not
    # read every note to throw them away.
    query = query.where(Entry.is_board == (want != "note"))  # noqa: E712
    for entry in session.scalars(query):
        row = _entry_row(entry, want=want)
        if row is not None:
            yield entry.id, row


def _register_all() -> None:
    """Every source, in one place, so adding a kind is one block of code."""
    from tessellate.core.database import (
        AskTurn,
        Attachment,
        Bookmark,
        Conversation,
        Document,
        Entry,
        MediaUpload,
        Recording,
        Reminder,
    )

    register(
        Source(
            name="notes",
            kind="note",
            slot=1,
            model=Entry,
            read=lambda obj: _entry_row(obj, want="note"),
            scan=lambda session: _scan_entries(session, want="note"),
        )
    )
    register(
        Source(
            name="boards",
            kind="board",
            slot=2,
            model=Entry,
            read=lambda obj: _entry_row(obj, want="board"),
            scan=lambda session: _scan_entries(session, want="board"),
        )
    )
    register(
        Source(
            name="maps",
            kind="map",
            #: The next free slot, not 2: slots are permanent, and a map row
            #: written under the boards slot before this source existed is
            #: moved by `reconcile_boards`, not reinterpreted.
            slot=8,
            model=Entry,
            read=lambda obj: _entry_row(obj, want="map"),
            scan=lambda session: _scan_entries(session, want="map"),
        )
    )
    register(
        Source(
            name="documents",
            kind="document",
            slot=3,
            model=Document,
            read=_document_row,
            scan=lambda session: (
                (doc.id, _document_row(doc)) for doc in session.scalars(select(Document))
            ),
        )
    )
    register(
        Source(
            name="attachments",
            kind="file",
            slot=4,
            model=Attachment,
            read=_attachment_row,
            scan=lambda session: (
                (att.id, _attachment_row(att)) for att in session.scalars(select(Attachment))
            ),
        )
    )
    register(
        Source(
            name="media",
            kind="file",
            slot=5,
            model=MediaUpload,
            read=_media_row,
            scan=lambda session: (
                (media.id, _media_row(media)) for media in session.scalars(select(MediaUpload))
            ),
        )
    )
    register(
        Source(
            name="bookmarks",
            kind="bookmark",
            slot=6,
            model=Bookmark,
            read=_bookmark_row,
            scan=lambda session: (
                (mark.id, _bookmark_row(mark)) for mark in session.scalars(select(Bookmark))
            ),
        )
    )
    register(
        Source(
            name="reminders",
            kind="reminder",
            slot=7,
            model=Reminder,
            read=_reminder_row,
            scan=lambda session: (
                (rem.id, _reminder_row(rem)) for rem in session.scalars(select(Reminder))
            ),
        )
    )
    register(
        Source(
            name="conversations",
            kind="chat",
            slot=9,
            model=Conversation,
            read=_conversation_row,
            scan=lambda session: (
                (conv.id, _conversation_row(conv)) for conv in session.scalars(select(Conversation))
            ),
        )
    )
    register(
        Source(
            name="ask_turns",
            kind="chat",
            slot=10,
            model=AskTurn,
            read=_ask_turn_row,
            scan=lambda session: (
                (turn.id, _ask_turn_row(turn)) for turn in session.scalars(select(AskTurn))
            ),
        )
    )
    register(
        Source(
            name="recordings",
            kind="recording",
            slot=11,
            model=Recording,
            read=_recording_row,
            scan=lambda session: (
                (rec.id, _recording_row(rec)) for rec in session.scalars(select(Recording))
            ),
        )
    )


def _document_row(doc) -> Row | None:  # noqa: ANN001
    #: A binned document is out of search until it is restored (5 item 10).
    if doc is None or getattr(doc, "deleted_at", None) is not None:
        return None
    flags = ["archived"] if getattr(doc, "archived_at", None) else []
    return Row(
        title=doc.title or "",
        body=doc.content or "",
        tags=getattr(doc, "file_type", "") or "",
        space=getattr(doc, "workspace_id", "default") or "default",
        flags=" ".join(flags),
        written=_written(getattr(doc, "created_at", None)),
    )


def _attachment_row(att) -> Row | None:  # noqa: ANN001
    """A file attached to a note: its name and whatever it says.

    The caption, the OCR text and the vision reading are one body rather than
    three columns: a person searching for a word in a scanned page does not
    know or care which extractor found it, and B3's promise is that the file's
    *text* is findable.
    """
    if att is None:
        return None
    from tessellate.core import readings

    return Row(
        title=att.filename or "",
        # Every reading, pages included (F10, `core/readings.text_of`).
        body=readings.text_of(att, "attachment"),
        tags=getattr(att, "mime", "") or "",
        space=getattr(att, "workspace_id", "default") or "default",
        written=_written(getattr(att, "created_at", None)),
    )


def _media_row(media) -> Row | None:  # noqa: ANN001
    if media is None:
        return None
    from tessellate.core import readings

    return Row(
        title=getattr(media, "original_name", "") or "",
        # Every reading (F10): the vision model's reading of an upload, and
        # its pages, were the two the search could not find words in.
        body=readings.text_of(media, "upload"),
        space=getattr(media, "workspace_id", "default") or "default",
        written=_written(getattr(media, "created_at", None)),
    )


def _bookmark_row(mark) -> Row | None:  # noqa: ANN001
    if mark is None:
        return None
    flags = ["pinned"] if getattr(mark, "pinned", False) else []
    return Row(
        title=mark.title or mark.url or "",
        body="\n".join(part for part in (mark.url, mark.note) if part),
        tags=getattr(mark, "group_name", "") or "",
        space=getattr(mark, "workspace_id", "default") or "default",
        flags=" ".join(flags),
        written=_written(getattr(mark, "created_at", None)),
    )


def _reminder_row(rem) -> Row | None:  # noqa: ANN001
    if rem is None or getattr(rem, "deleted_at", None) is not None:
        return None
    flags = ["done"] if getattr(rem, "done", False) else ["open"]
    if getattr(rem, "priority", "") == "high":
        flags.append("urgent")
    return Row(
        title=rem.text or "",
        body=rem.text or "",
        space=getattr(rem, "workspace_id", "default") or "default",
        flags=" ".join(flags),
        written=_written(getattr(rem, "due_at", None)),
    )


def _conversation_row(conv) -> Row | None:  # noqa: ANN001
    """A saved chat: its title, and every turn's words as one body.

    One row per chat rather than per message: the rowid is the chat's id
    (`_rowid`), and a hit opens the chat, which is where its turns are read.
    """
    if conv is None:
        return None
    try:
        messages = json.loads(conv.messages or "[]")
    except (TypeError, ValueError):
        messages = []
    words = [
        message["content"]
        for message in (messages if isinstance(messages, list) else [])
        if isinstance(message, dict) and isinstance(message.get("content"), str) and message["content"].strip()
    ]
    flags = []
    if getattr(conv, "pinned", False):
        flags.append("pinned")
    if getattr(conv, "archived_at", None):
        flags.append("archived")
    return Row(
        title=conv.title or "",
        body="\n".join(words),
        space=getattr(conv, "workspace_id", "default") or "default",
        flags=" ".join(flags),
        written=_written(getattr(conv, "created_at", None)),
    )


def _ask_turn_row(turn) -> Row | None:  # noqa: ANN001
    """One question asked in the Ask box, with its answer."""
    if turn is None:
        return None
    return Row(
        title=turn.question or "",
        body="\n".join(part for part in (turn.question, turn.answer) if part),
        space=getattr(turn, "workspace_id", "default") or "default",
        flags="pinned" if getattr(turn, "pinned", False) else "",
        written=_written(getattr(turn, "created_at", None)),
    )


def _recording_row(rec) -> Row | None:  # noqa: ANN001
    """A kept recording: its name and the lines said in it.

    A take still being made (`state` "recording") and one in the bin are out,
    as a binned document is; the transcript lines are joined without their
    timings, which a search has no use for (the recording's own sheet seeks)."""
    if rec is None or getattr(rec, "deleted_at", None) is not None or rec.state != "saved":
        return None
    from tessellate.core import transcript

    from tessellate.core import recordings

    spoken = " ".join(str(seg.get("text") or "").strip() for seg in transcript.loads(rec.segments))
    #: The comments pressed onto marks while recording ("ask about the retry
    #: budget") are words the person wrote about the recording; they were the
    #: one thing on it a search could not find.
    marked = " ".join(mark["note"].strip() for mark in recordings.marks_of(rec) if mark["note"].strip())
    return Row(
        title=rec.title or "Recording",
        body=" ".join(part for part in (spoken.strip(), marked) if part),
        tags=rec.derived or "",
        space=getattr(rec, "workspace_id", "default") or "default",
        written=_written(getattr(rec, "created_at", None)),
    )


#: Sources added after notebooks had already been indexed. The write path only
#: sees what changes from now on, so a chat saved before chats were a kind
#: would never be found; `reconcile_sources` fills each one once.
_LATE_SOURCES = ("conversations", "ask_turns", "recordings")


def reconcile_sources(session: Session) -> bool:
    """Index a late source whose slot is empty while its table is not.

    Returns True when anything was written. Run at every startup after the
    table exists, beside `reconcile_boards`: a check of two `LIMIT 1` reads
    once a notebook has been filled, so the second startup is a no-op.
    """
    if _table_missing(session):
        return False
    connection = session.connection()
    changed = False
    for name in _LATE_SOURCES:
        source = _SOURCES[name]
        low, high = source.slot * SLOT_STRIDE, (source.slot + 1) * SLOT_STRIDE
        held = connection.exec_driver_sql(
            "SELECT 1 FROM search_index WHERE rowid >= ? AND rowid < ? LIMIT 1", (low, high)
        ).first()
        if held is not None or session.scalars(select(source.model.id).limit(1)).first() is None:
            continue
        for ref_id, row in source.scan(session):
            _write(connection, source, ref_id, row)
            changed = changed or row is not None
    return changed


_register_all()
