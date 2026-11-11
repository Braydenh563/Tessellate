"""Hard delete, the recycle bin's purge, and attachments: split out of
`entry/manager.py` (audit-1028 K24, dec-1111-k2.md). Moved whole and
unchanged: `board_type_of`, `seal_private_events`, the dependent-row deletes,
`purge_entries`, `empty_recycle_bin`, `purge_expired_deleted`, and the
attachment functions. Callers import these names from here. It imports
`log_action` from `entry.manager` and nothing there imports it back.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from pathlib import Path

from tessellate.core.database import (
    Attachment,
    ChunkVector,
    EmbeddingRecord,
    EntityMention,
    Entry,
    DerivedFact,
    DocumentLink,
    EntryBookmark,
    EntryDate,
    EntryOpen,
    EntryLink,
    EntryProperty,
    EntryRevision,
    NoteScore,
    Reminder,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
    utcnow,
)
from tessellate.core import events, paths, reading_bin
from tessellate.entry.manager import (
    log_action,
)


def board_type_of(entry: Entry | None) -> str:
    """"map" or "board" for a note that is one.

    A one-line read of `Entry.board_settings`, duplicated from
    `routes_whiteboard._board_settings` rather than imported: `entry/manager`
    is the layer the API sits on top of, and importing an API module from
    here would invert that (and, in practice, import a router at delete time).
    Tolerant of every shape a JSON text column can hold, for the same reason
    the original is: a bad value must degrade to "an ordinary board", never
    to an exception in the middle of emptying the bin.

    Public, and takes the row rather than an id, because a second caller
    turned up (`routes_entries._reference_rows`, which already has the
    `Entry` in hand and was about to write this parse a third time). The
    id version below is kept for the callers that only have an id.
    """
    if entry is None:
        return "board"
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        return "board"
    if not isinstance(parsed, dict):
        return "board"
    return "map" if parsed.get("type") == "map" else "board"


def _board_type_of(session: Session, board_id: int) -> str:
    """"map" or "board" for the note with this id."""
    return board_type_of(session.get(Entry, board_id))


#: The one shape a whiteboard image url may take, the same allowlist as
#: `routes_whiteboard.MEDIA_URL_RE`, repeated here rather than imported because
#: the entry manager must not depend on a route module.
_MEDIA_URL_RE = re.compile(r"^/media/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


def seal_private_events(session: Session, ids: list[int]) -> None:
    """Mark every event about these (private) notes as sealed, and empty it.

    The activity export leaves out events about a private note by looking the
    note up (`routes_settings._not_private_events`), and a purged note is
    gone, so that lookup stops matching and its events, which carry a title or
    a clip of it in `detail` and the whole text in `payload`, would be handed
    over. A purge seals them first: `detail` dropped, `payload` replaced by
    the flag the export reads. The history of a note that no longer exists
    cannot be replayed or undone anyway.
    """
    if not ids:
        return
    from tessellate.core.database import AuditLog

    session.flush()
    session.execute(
        update(AuditLog)
        .where(AuditLog.entity_type.in_(("entry", "note", "entries")), AuditLog.entity_id.in_(ids))
        .values(detail=None, payload={"private": True})
    )


def _forget_board_thumbs(uploads_dir: Path | None, ids: list[int]) -> None:
    """A purged board's stored thumbnail goes with it."""
    if uploads_dir is None:
        return
    # uploads/ sits in the data folder; reading it from config here would
    # import the API's deps layer from the entry layer (a cycle).
    from tessellate.core import board_thumbs

    try:
        board_thumbs.forget(uploads_dir.parent, ids)
    except OSError:  # a stuck thumbnail must not block a purge
        pass


def _delete_attachments_and_vectors(session: Session, ids: list[int], uploads_dir: Path | None) -> None:
    """The attached files, the search index rows, the vectors and the links of the entries being purged."""
    # Attached files: remove bytes from disk (best effort) then the rows.
    attachments = list(
        session.scalars(select(Attachment).where(Attachment.entry_id.in_(ids)))
    )
    for attachment in attachments:
        if uploads_dir is not None:
            try:
                _upload_path(uploads_dir, attachment.stored_name).unlink(missing_ok=True)
            except OSError as exc:
                # The row goes either way, a file that won't delete must not
                # block the purge: but a folder that has stopped accepting
                # deletes will otherwise grow forever with nothing said.
                logging.getLogger("tessellate.entries").warning(
                    "couldn't delete the file for attachment %s (%s); "
                    "removing the record anyway",
                    attachment.id,
                    type(exc).__name__,
                )
    # The search index hangs off the ORM flush, and the two DELETEs here are
    # statements the flush never sees, so their rows are taken out by hand.
    from tessellate.search import index as search_index

    attachment_ids = [a.id for a in attachments]
    search_index.forget(session, Attachment, attachment_ids)
    reading_bin.forget_page_reads(session, "attachment", attachment_ids)
    search_index.forget(session, Entry, ids)
    session.execute(delete(Attachment).where(Attachment.entry_id.in_(ids)))
    session.execute(delete(EmbeddingRecord).where(EmbeddingRecord.entry_id.in_(ids)))
    session.execute(delete(ChunkVector).where(ChunkVector.entry_id.in_(ids)))
    # The table, not the mapped class: the class carries the space filter, and a link
    # stamped for another space would survive its note (every space's, as the delete is).
    links = EntryLink.__table__
    session.execute(delete(links).where(or_(links.c.source_entry_id.in_(ids), links.c.target_entry_id.in_(ids))))


def _delete_entry_dependents(session: Session, ids: list[int]) -> None:
    """Every table that holds a foreign key to `entries.id`, or the purge fails outright."""
    # **Everything else that points at an entry, or the delete fails outright.**
    #
    # Reported twice in one sitting, "request failed (500) when I tried to
    # empty the bin", and two particular notes that could not be deleted at
    # all. One cause: `PRAGMA foreign_keys=ON` is set (database.py), so a row
    # left behind in *any* of these tables makes `DELETE FROM entries` raise
    # IntegrityError, which surfaces as a 500 and leaves the bin exactly as it
    # was. The notes in the report both carried a resolved time phrase, the
    # `this week → week of 27 July` chip is an `entry_dates` row: which is
    # why those two and not the rest.
    #
    # These four were added to the schema after `_hard_delete` was written, and
    # each was invisible until a note happened to have one. Anything that gains
    # a `ForeignKey("entries.id")` from here has to be listed here too; the
    # test added alongside this fails if one is missed.
    session.execute(delete(EntryRevision).where(EntryRevision.entry_id.in_(ids)))
    session.execute(delete(EntryDate).where(EntryDate.entry_id.in_(ids)))
    session.execute(delete(DocumentLink).where(DocumentLink.entry_id.in_(ids)))
    # Three more that arrived after the four above, each invisible until a
    # note happened to have one, and each producing the same 500 with the
    # note still in the bin. `EntryBookmark` is a saved link attached to this
    # note and `EntityMention` a person or project found in it: both are
    # *about* the note and have nothing to say once it is gone. `NoteScore`
    # is a cache of how faded the note is (`ai/resurface.py`), and a cache
    # that outlives what it describes is how a deleted note reappears in a
    # panel.
    #
    # The list above is no longer kept by memory: `test_recycle_bin.py` reads
    # every `ForeignKey("entries.id")` out of the metadata and fails if one
    # is not handled here, because remembering is what failed the first three
    # times.
    session.execute(delete(EntryBookmark).where(EntryBookmark.entry_id.in_(ids)))
    session.execute(delete(EntityMention).where(EntityMention.entry_id.in_(ids)))
    session.execute(delete(NoteScore).where(NoteScore.entry_id.in_(ids)))
    # KG4: a note's property index is about the note.
    session.execute(delete(EntryProperty).where(EntryProperty.entry_id.in_(ids)))
    # Section 17 row 5: the day-by-day open counts are about the note.
    session.execute(delete(EntryOpen).where(EntryOpen.entry_id.in_(ids)))
    # An eighth, added with the derived facts table (I9): what the app
    # worked out about a note is about the note, so it goes when the note
    # does. Keeping it would also leave the "what the notebook learned"
    # list citing a span in a note nobody can open.
    session.execute(delete(DerivedFact).where(DerivedFact.entry_id.in_(ids)))
    # A whiteboard card *is* its note, with the note gone there is nothing
    # left to show, so the card goes with it, same as a sketch's own delete.
    session.execute(delete(WhiteboardNode).where(WhiteboardNode.entry_id.in_(ids)))


def _detach_board_contents(session: Session, ids: list[int], uploads_dir: Path | None) -> None:
    """A purged map takes its own contents (and image files) with it; an ordinary board's are detached."""
    # `board_id` is a different relationship: it names which board a card or
    # sketch lives *on*, and that board is itself just a note. Purging the
    # board note must not take every card on it with it, that would be
    # "delete this one note" silently wiping an entire whiteboard. Detached to
    # the default board instead, the same "orphan becomes a root" choice
    # already made for `Entry.parent_id` below.
    session.execute(
        WhiteboardNode.__table__.update()
        .where(WhiteboardNode.board_id.in_(ids))
        .values(board_id=None)
    )
    session.execute(
        WhiteboardSketch.__table__.update()
        .where(WhiteboardSketch.board_id.in_(ids))
        .values(board_id=None)
    )
    # **A map contains its own contents; an ordinary board does not.**
    #
    # The rule, asked for in those words ("any and all text boxes and things
    # that are in the map stay bundled within the map"), and the reason the
    # objects on a board being purged are split in two here rather than all
    # detached alike:
    #
    # - a `topic` exists only in the map. Detaching it dumps loose text onto
    #   the one board nobody ever deletes, which is how a deleted map comes
    #   back as litter on the default board;
    # - a `note`/`document`/`file`/`link` node is a *pointer* at something in
    #   the library. The pointer goes with the map; the thing it pointed at
    #   is a note, and notes are not deleted by deleting a picture of one.
    #   That distinction is the whole of `tests/test_mindmap.py`'s first test;
    # - everything on a plain whiteboard keeps the behaviour it always had, 
    #   detached, not destroyed. See the comment above: "delete this one
    #   note" must not silently wipe an entire whiteboard.
    map_board_ids = [
        board_id
        for board_id in ids
        if _board_type_of(session, board_id) == "map"
    ]
    if map_board_ids:
        # A map's objects go with it, so the image files behind them go too
        # (BACKLOG §116.1 item 1, dropped from backend sprint 2). The same
        # allowlist `routes_whiteboard._media_path` applies: only a url that
        # resolves *inside* `<data>/media` is ever unlinked, so a legacy or
        # hand-edited row cannot turn a purge into "delete any file". Objects
        # on an ordinary board are detached below, not deleted, and keep
        # their files. `uploads_dir` and the media folder are siblings by
        # construction (config.py); nothing else here knows the data dir.
        if uploads_dir is not None:
            media_dir = (uploads_dir.parent / "media").resolve()
            doomed = session.scalars(
                select(WhiteboardObject).where(
                    WhiteboardObject.board_id.in_(map_board_ids),
                    WhiteboardObject.kind == "image",
                )
            )
            for obj in doomed:
                try:
                    url = str(json.loads(obj.data or "{}").get("url") or "")
                    if not _MEDIA_URL_RE.match(url):
                        continue
                    path = (media_dir / url.removeprefix("/media/")).resolve()
                    if path.is_relative_to(media_dir):
                        path.unlink(missing_ok=True)
                except (OSError, ValueError, TypeError) as exc:
                    logging.getLogger("tessellate.entries").warning(
                        "couldn't delete the file for whiteboard image %s (%s); "
                        "removing the record anyway",
                        int(obj.id),
                        type(exc).__name__,
                    )
        session.execute(
            delete(WhiteboardObject).where(WhiteboardObject.board_id.in_(map_board_ids))
        )
    session.execute(
        WhiteboardObject.__table__.update()
        .where(WhiteboardObject.board_id.in_(ids))
        .values(board_id=None)
    )


def _hard_delete(session: Session, entries: list[Entry], uploads_dir: Path | None = None) -> int:
    """Permanently remove entries plus their vectors, links, and files."""
    ids = [e.id for e in entries]
    if not ids:
        return 0
    _forget_board_thumbs(uploads_dir, ids)
    seal_private_events(session, [e.id for e in entries if e.is_private])
    _delete_attachments_and_vectors(session, ids, uploads_dir)
    _delete_entry_dependents(session, ids)
    _detach_board_contents(session, ids, uploads_dir)
    # A reminder's entry is optional, so it is detached rather than deleted:
    # "water the tomatoes" is still a thing you asked to be reminded of after
    # the note that prompted it has gone, and deleting the reminder would throw
    # away something the user set by hand.
    session.execute(
        Reminder.__table__.update()
        .where(Reminder.entry_id.in_(ids))
        .values(entry_id=None)
    )
    # Orphan children of a purged parent become thread roots.
    session.execute(
        Entry.__table__.update()
        .where(Entry.parent_id.in_(ids))
        .values(parent_id=None)
    )
    session.execute(delete(Entry).where(Entry.id.in_(ids)))
    return len(ids)


@events.writes("entry", "purged")
def purge_entries(
    session: Session, entries: list[Entry], uploads_dir: Path | None = None
) -> int:
    """Permanently delete specific notes. Commits.

    The named half of `_hard_delete`, so "delete this one for good" and "empty
    the bin" destroy a note by exactly the same code, vectors, links, files,
    and re-parenting any replies. Two implementations of permanent deletion is
    how one of them ends up leaving an orphaned embedding behind, which is a
    note that is gone from the list and still findable by search.
    """
    ids = [entry.id for entry in entries]
    private_ids = [entry.id for entry in entries if entry.is_private]
    count = _hard_delete(session, entries, uploads_dir=uploads_dir)
    if count:
        # One event carrying the id list, never one per row: a purge is a
        # single thing the user did, and a bin emptied of two hundred notes
        # would otherwise bury every other event in the log under its own
        # bookkeeping (Brief 7's contract, `tests/test_events.py`).
        log_action(
            session,
            "purged",
            "entry",
            ids[0],
            f"{count} entries",
            payload={"ids": ids, "count": count},
        )
        # The purge event is itself about the first id; sealed when that was private.
        seal_private_events(session, private_ids[:1] if private_ids[:1] == ids[:1] else [])
    session.commit()
    return count


@events.writes("recycle_bin", "purged")
def empty_recycle_bin(session: Session, uploads_dir: Path | None = None) -> int:
    """Manual 'empty now'. Commits."""
    binned = list(session.scalars(select(Entry).where(Entry.is_deleted == True)))  # noqa: E712
    ids = [entry.id for entry in binned]
    count = _hard_delete(session, binned, uploads_dir=uploads_dir)
    if count:
        log_action(
            session,
            "purged",
            "recycle_bin",
            detail=f"{count} entries",
            payload={"ids": ids, "count": count},
        )
    session.commit()
    return count


@events.writes("recycle_bin", "purged")
def purge_expired_deleted(
    session: Session, days: int, uploads_dir: Path | None = None
) -> int:
    """Auto-clear: permanently drop entries binned more than `days` ago.
    Runs at every startup. Commits."""
    cutoff = utcnow() - timedelta(days=days)
    expired = list(
        session.scalars(
            select(Entry).where(
                Entry.is_deleted == True,  # noqa: E712
                Entry.deleted_at < cutoff,
            )
        )
    )
    ids = [entry.id for entry in expired]
    count = _hard_delete(session, expired, uploads_dir=uploads_dir)
    if count:
        log_action(
            session,
            "purged",
            "recycle_bin",
            detail=f"{count} expired entries",
            payload={"ids": ids, "count": count, "days": days},
        )
    session.commit()
    return count


# --- attachments ------------------------------------------------------


def add_attachment(
    session: Session,
    entry: Entry,
    filename: str,
    stored_name: str,
    mime: str,
    size: int,
) -> Attachment:
    attachment = Attachment(
        entry_id=entry.id,
        filename=filename,
        stored_name=stored_name,
        mime=mime,
        size=size,
    )
    session.add(attachment)
    session.flush()
    log_action(session, "attached", "entry", entry.id, filename)
    session.commit()
    return attachment


def attachments_for(session: Session, entry: Entry) -> list[Attachment]:
    return list(
        session.scalars(
            select(Attachment)
            .where(Attachment.entry_id == entry.id)
            .order_by(Attachment.id)
        )
    )


def attachments_for_entries_bulk(
    session: Session, entry_ids: list[int]
) -> dict[int, list[Attachment]]:
    """`attachments_for` for several notes in one query, grouped by note id.

    The fourth of these batched forms, and the one that was missed:
    `_to_out_bulk` already passed pre-fetched categories, dates, documents and
    links, so `GET /entries` looked bulk-fetched, while `_to_out`'s
    `attachments=` list still called `attachments_for` once per row. Measured
    with a statement counter on a 60-note page: 67 statements, 60 of them the
    same `SELECT ... FROM attachments WHERE entry_id = ?`. It is the notes
    list, the most-requested endpoint in the app, so it was also the most
    expensive place in the schema to leave one.
    """
    if not entry_ids:
        return {}
    out: dict[int, list[Attachment]] = {}
    rows = session.scalars(
        select(Attachment).where(Attachment.entry_id.in_(entry_ids)).order_by(Attachment.id)
    )
    for attachment in rows:
        out.setdefault(attachment.entry_id, []).append(attachment)
    return out


def _upload_path(uploads_dir: Path, stored_name: str) -> Path:
    """`uploads_dir / stored_name`, refused (OSError, which every caller
    already treats as "leave the file") when the name reaches outside the
    folder: a stored name comes from the database, and a restored database
    is not trusted (audit 1028 K7)."""
    try:
        return paths.contained(uploads_dir, stored_name)
    except paths.OutsideFolder:
        raise OSError("attachment path outside the uploads folder") from None


def delete_attachment(
    session: Session, attachment: Attachment, uploads_dir: Path
) -> None:
    try:
        _upload_path(uploads_dir, attachment.stored_name).unlink(missing_ok=True)
    except OSError:
        pass  # a stuck file shouldn't block removing the record
    log_action(session, "detached", "entry", attachment.entry_id, attachment.filename)
    reading_bin.forget_page_reads(session, "attachment", [attachment.id])
    session.delete(attachment)
    session.commit()


#: Windows treats these as reserved regardless of extension, `CON.txt` is as
#: unusable as `CON`. Checked against the name's stem, case-insensitively,
#: because this app runs on Windows via start.bat and a name that is fine on
#: Linux but unusable the moment someone opens the same data folder there is
#: the kind of bug that only shows up on the other platform.
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Matches `Attachment.filename`'s own column width, a name the DB would
#: truncate silently is rejected instead, before it is ever stored half-cut.
MAX_ATTACHMENT_FILENAME = 255


def validate_attachment_filename(name: str) -> str:
    """A display name safe to store and to echo into a download header.

    This is the *label* a person sees and renames, `stored_name` (a random
    uuid) is what the disk and every path on disk actually use, and never
    changes here. That split is what makes this a strict reject-and-explain
    check rather than `routes_files.safe_filename`'s silent rewrite: nothing
    here is ever written to a filesystem path, so there is no "make it safe"
    fallback to reach for, only "tell the user why their name didn't work."

    Still validated as if it *were* a path component, because the failure
    mode of skipping that is not hypothetical for this app specifically: the
    name is handed to Starlette's `FileResponse(filename=...)` on every
    download, which puts it straight into a `Content-Disposition` header, and
    a control character or a name that is just `..` is exactly the kind of
    input that check is supposed to catch before it reaches a header or a
    person's screen.
    """
    if name is None or not name.strip():
        raise ValueError("A filename is required.")
    if "\x00" in name:
        raise ValueError("Filenames can't contain null bytes.")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in name):
        raise ValueError("Filenames can't contain control characters.")
    cleaned = name.strip()
    if len(cleaned) > MAX_ATTACHMENT_FILENAME:
        raise ValueError(f"Filenames can't be longer than {MAX_ATTACHMENT_FILENAME} characters.")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("Filenames can't contain a path separator.")
    if ".." in cleaned:
        raise ValueError("Filenames can't contain '..'.")
    if re.match(r"^[A-Za-z]:[/\\]?", cleaned):
        raise ValueError("Filenames can't be an absolute path.")
    if cleaned.startswith("."):
        raise ValueError("Filenames can't start with a dot.")
    stem = cleaned.split(".", 1)[0].strip().upper()
    if stem in _RESERVED_WINDOWS_NAMES:
        raise ValueError(f"'{cleaned}' is a reserved system name and can't be used.")
    return cleaned


def rename_attachment(session: Session, attachment: Attachment, new_filename: str) -> Attachment:
    """Change what a file is *called*, never what it *is* on disk.

    Only `filename`, the Library label and the download's suggested name , 
    changes. `stored_name` (the uuid on disk) and `mime` (recorded at upload,
    from the browser's own `Content-Type`) are left alone, which is what lets
    `validate_attachment_filename` above be a strict allowlist instead of an
    extension allowlist: the bytes `/files/{id}` serves back and the
    `Content-Type` it serves them as never change because of a rename, only
    the label on the download dialog does.

    Raises `ValueError` for a name `validate_attachment_filename` rejects,
    and `FileExistsError` if another file on the *same* note already has that
    name: collisions are scoped per-note, the same boundary the Library
    already draws around what's confusable with what.
    """
    cleaned = validate_attachment_filename(new_filename)
    collision = session.scalar(
        select(Attachment).where(
            Attachment.entry_id == attachment.entry_id,
            Attachment.id != attachment.id,
            Attachment.filename == cleaned,
        )
    )
    if collision is not None:
        raise FileExistsError(f"'{cleaned}' is already used on this note.")
    if cleaned != attachment.filename:
        attachment.filename = cleaned
        log_action(session, "renamed", "entry", attachment.entry_id, f"renamed a file to {cleaned}")
        session.commit()
    return attachment
