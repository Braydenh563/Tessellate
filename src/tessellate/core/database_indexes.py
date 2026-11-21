"""The startup index work of `DatabaseManager`, moved whole out of `database.py`.

`_ensure_fts5` (the full-text index and its triggers), the `_INDEXES` and
`_UNIQUE_INDEXES` tables, `_ensure_readings_view` and `_ensure_indexes`
touch only `self.engine`, so they sit in a mixin that imports nothing from
`database`: the pair stays acyclic and `DatabaseManager` inherits them.
"""

from __future__ import annotations

import logging
from typing import Any


class IndexesMixin:
    engine: Any

    def _ensure_fts5(self) -> None:
        """An FTS5 index over `entries`, kept in sync by triggers.

        ROADMAP.md item 32: `keyword_search` used to be a leading-wildcard
        `ILIKE`, which no index can serve, plus a hand-rolled integer score
        that treats a rare word the same as a common one. FTS5's own
        `bm25()` gives real IDF-weighted relevance, already in SQLite, no
        new dependency: for the cost of one virtual table.

        `content='entries', content_rowid='id'` makes this an *external
        content* table: FTS5 stores only its own index, not a second copy
        of the text, and `entries.id` already is the SQLite rowid (a plain
        `INTEGER PRIMARY KEY` column is a rowid alias). The three triggers
        are what an external-content table needs instead of the automatic
        upkeep a normal table gets from the ORM, SQLite doesn't have
        anything that reaches into a virtual table on its own, so every
        write path (the ORM, a raw migration script, anything future) stays
        in sync for free rather than needing to remember to call something.
        `IF NOT EXISTS` throughout makes this safe to run on every startup,
        the same additive convention `_add_missing_columns` already uses.
        """
        with self.engine.begin() as connection:
            # Stemming, so "proving" finds "prove" and "proved", and "boots"
            # finds "boot". The index shipped on FTS5's default tokenizer,
            # which matches whole words only; with no AI running keyword
            # search is the whole of search, and a query in a different
            # inflection than the note found nothing. `porter unicode61`
            # is built into SQLite's FTS5, no dependency. A tokenizer is
            # fixed at CREATE time, so an index built before this has to be
            # rebuilt once: the table's own DDL in sqlite_master says which
            # it is, and dropping the index (never the notes: it is an
            # external-content table holding no text of its own) lets the
            # back-fill below repopulate it, guarded by the trigger it also
            # drops.
            existing_ddl = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries_fts'"
            ).scalar()
            if existing_ddl and "porter" not in existing_ddl:
                for trigger in ("entries_fts_ai", "entries_fts_ad", "entries_fts_au"):
                    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {trigger}")
                connection.exec_driver_sql("DROP TABLE IF EXISTS entries_fts_vocab")
                connection.exec_driver_sql("DROP TABLE IF EXISTS entries_fts")
            connection.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5("
                "content, tags, content='entries', content_rowid='id', "
                "tokenize='porter unicode61'"
                ")"
            )
            # The index's own vocabulary as a table, one row per distinct
            # term, maintained by FTS5 itself. `keyword_search` reads it to
            # correct a misspelt query word to the nearest word the notebook
            # actually contains ("sourdogh" → "sourdough"), which is the
            # cheap, honest form of typo tolerance: it can only ever suggest
            # words that exist in the notes, and it costs one range scan on
            # the term's first letter rather than a second index.
            connection.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts_vocab "
                "USING fts5vocab('entries_fts', 'row')"
            )
            # A fresh virtual table starts empty even when `entries` already
            # has rows (a database from before this existed), the
            # external-content trick means FTS5 never scanned the real table
            # on its own. `INSERT INTO ... SELECT` once, guarded by the
            # trigger's own existence so it can't re-run and duplicate rows
            # on every subsequent startup.
            already_wired = connection.exec_driver_sql(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='trigger' AND name='entries_fts_ai'"
            ).scalar()
            if not already_wired:
                connection.exec_driver_sql(
                    "INSERT INTO entries_fts(rowid, content, tags) "
                    "SELECT id, content, tags FROM entries"
                )
            connection.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS entries_fts_ai "
                "AFTER INSERT ON entries BEGIN "
                "INSERT INTO entries_fts(rowid, content, tags) "
                "VALUES (new.id, new.content, new.tags); "
                "END"
            )
            connection.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS entries_fts_ad "
                "AFTER DELETE ON entries BEGIN "
                "INSERT INTO entries_fts(entries_fts, rowid, content, tags) "
                "VALUES ('delete', old.id, old.content, old.tags); "
                "END"
            )
            connection.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS entries_fts_au "
                "AFTER UPDATE ON entries BEGIN "
                "INSERT INTO entries_fts(entries_fts, rowid, content, tags) "
                "VALUES ('delete', old.id, old.content, old.tags); "
                "INSERT INTO entries_fts(rowid, content, tags) "
                "VALUES (new.id, new.content, new.tags); "
                "END"
            )

    #: The list queries that run on essentially every page load, and the
    #: composite index each one needs to be served from an index instead of a
    #: sort. Kept as data in one place rather than as `Index()` objects on the
    #: model, for a reason worth stating: `create_all()` "creates missing
    #: tables only" (see its call site above), so an index declared on an
    #: already-existing table would be created on a *fresh* database and
    #: silently never appear on anybody's real one: the same
    #: works-on-a-new-profile-only trap `_add_missing_columns` exists to avoid
    #: for columns.
    #:
    #: The column order in each is the query's own shape: equality filters
    #: first, then the ORDER BY terms in order and in their own direction.
    #: SQLite will only skip the sort if the index's trailing columns match
    #: the ORDER BY exactly, direction included, which is why `pinned DESC`
    #: is spelled out rather than left to default ASC.
    _INDEXES: tuple[tuple[str, str], ...] = (
        # manager.list_entries(), the Notes tab, GET /entries, and most
        # background jobs. Measured before this existed: EXPLAIN QUERY PLAN
        # reported "USE TEMP B-TREE FOR ORDER BY", i.e. SQLite sorted every
        # live note in the notebook on every call.
        (
            "ix_entries_live",
            "entries (workspace_id, is_deleted, archived_at, "
            "pinned DESC, created_at DESC, id DESC)",
        ),
        # manager.list_deleted_entries(), the recycle bin.
        (
            "ix_entries_bin",
            "entries (workspace_id, is_deleted, deleted_at DESC, id DESC)",
        ),
        # manager.list_archived_entries(), the archive.
        (
            "ix_entries_archive",
            "entries (workspace_id, is_deleted, archived_at DESC, id DESC)",
        ),
        # routes_library._notes() and routes_graph's entry scan both add
        # `is_draft = 0` to the live filter; without `is_draft` in an index
        # they fall back to the same full scan the live index above removes.
        (
            "ix_entries_live_nodraft",
            "entries (workspace_id, is_deleted, is_draft, archived_at, "
            "created_at DESC, id DESC)",
        ),
        # PLAN.md §0 P5 / AUDIT.md B10's remaining, unverified columns.
        # `Entry.category_id`, a plain ForeignKey column carries no index of
        # its own in SQLAlchemy/SQLite, is scanned by "notes in category X"
        # (`entry/manager.py`'s `category_entry_ids`/`move_category_entries`)
        # and by every `/library` row that resolves a note's category name.
        ("ix_entries_category_id", "entries (category_id)"),
        # `Attachment.entry_id`, same gap: an unindexed ForeignKey, searched
        # both singly (a note opening its own attachments) and via `IN (...)`
        # over a page of notes (`/library`'s thumbnail lookup,
        # `entry/manager.py`'s bulk delete). Measured: without this, the
        # `IN` lookup above does a full table scan of `attachments` per page.
        ("ix_attachments_entry_id", "attachments (entry_id)"),
        # GET /media (`routes_files.list_media`) orders every upload by
        # `created_at DESC` inside the workspace filter `WorkspaceMixin`
        # already adds: measured "USE TEMP B-TREE FOR ORDER BY" on 5,000
        # uploads without this; the single-column `workspace_id` index the
        # mixin gives every table isn't enough once an ORDER BY is added on
        # top of the equality filter.
        ("ix_media_uploads_workspace_created", "media_uploads (workspace_id, created_at DESC)"),
        # GET /documents (`routes_documents.list_documents`) is the same
        # shape one predicate wider: workspace-scoped, `archived_at IS NULL`,
        # ordered by `updated_at DESC`, same measured TEMP B-TREE without a
        # composite index that includes the sort column.
        (
            "ix_documents_workspace_live_updated",
            "documents (workspace_id, archived_at, updated_at DESC)",
        ),
        # `PageRead(kind, source_id)`, named in the same audit item, turns
        # out to already be covered: `uq_page_read_source_page`'s own unique
        # constraint is itself an index on `(kind, source_id, page)`, and
        # SQLite serves both `_remember_page_read`'s single-row lookup and
        # `_stored_page_reads`'s `kind=? AND source_id IN (...)` scan from
        # its `(kind, source_id)` prefix with no SCAN (checked with EXPLAIN
        # QUERY PLAN, not assumed), so no new index is added for it here.
        #
        # `events.events_for`, which is a note's History sheet, every replay
        # and every restore (WORLD_CLASS_PLAN B1, Brief 7): it filters
        # `entity_type` and `entity_id` and orders by `id DESC`, and neither
        # filter column was indexed, so opening one note's history read the
        # whole of `audit_log`. That table only grows, and grows fastest on
        # the notebooks that are used most, so this is the one index here
        # whose absence gets worse rather than staying merely wasteful.
        # Measured on 60,000 events over 2,000 notes: "SCAN audit_log" at
        # 6.390 ms per request became "SEARCH audit_log USING INDEX
        # ix_audit_log_entity" at 0.082 ms. `id DESC` is in the index so the
        # newest-first page is a walk backwards along it rather than a sort
        # of everything that matched.
        ("ix_audit_log_entity", "audit_log (entity_type, entity_id, id DESC)"),
        # `EntryLink.source_entry_id` and `.target_entry_id`, the link table
        # of a linked-notes app and the largest remaining gap. Both are plain
        # ForeignKey columns, so neither carried an index, and every lookup
        # is `source = ? OR target = ?`: a note opening its own connections,
        # `links_for_entries_bulk` for a page of the notes list, the graph
        # build, and the two-hop walk `search/engine._hops_from` does per
        # search. Measured on 2,000 notes with 6,000 links, three per note:
        # "SCAN entry_links", and `links_for_entries_bulk` over a 50-note
        # page at 8.78 ms. Two single-column indexes rather than one
        # composite, because the OR means SQLite serves each side from its
        # own index and unions the rowids; a composite on (source, target)
        # would only serve the source half.
        ("ix_entry_links_source", "entry_links (source_entry_id)"),
        ("ix_entry_links_target", "entry_links (target_entry_id)"),
        # `WhiteboardObject.board_id`, the same shape: every open of a
        # whiteboard or mind map reads its objects by board, and the table
        # holds every object of every board. Measured on one board of 3,000
        # objects: "SCAN whiteboard_objects", 34.38 ms to read that board.
        ("ix_whiteboard_objects_board", "whiteboard_objects (board_id)"),
        # `Conversation` and `Reminder` list newest-first inside the
        # workspace filter the mixin adds, and both reported "USE TEMP
        # B-TREE FOR ORDER BY": the same shape as the media and documents
        # indexes above, which is why they take the same form.
        ("ix_conversations_workspace_updated", "conversations (workspace_id, updated_at DESC)"),
        ("ix_reminders_workspace_due", "reminders (workspace_id, due_at DESC)"),
        # `note_scores`, read newest-faded-first on every resurfacing request
        # (WORLD_CLASS_PLAN I4). The ORDER BY is the whole query, so without
        # this SQLite sorts every scored note to find three: measured at 800
        # notes, adding a LIMIT alone moved the read from 23.0 ms to 58.7 ms,
        # because a LIMIT over an unindexed sort still sorts everything and
        # then throws it away. The index is the half that makes the LIMIT
        # mean something.
        ("ix_note_scores_rank", "note_scores (score DESC, entry_id DESC)"),
        # The foreign keys a note is looked up by that still carried no index
        # (the performance pass, 2026-10-03, INBOX 441). Each is "this note's
        # ...": its replies (`entries.parent_id`), the boards it is on and a
        # board's cards (`whiteboard_nodes`), a board's sketches, its
        # reminders and its bookmarks. SQLite also reads the child column of
        # every foreign key on every delete of the parent, so with
        # `foreign_keys=ON` an unindexed one is a table scan per deleted note.
        # Measured on 5,000 notes with 4,000 board cards and 1,500 reminders:
        # 900 lookups by these columns, 604 ms unindexed, 2.9 ms indexed.
        ("ix_entries_parent", "entries (parent_id)"),
        ("ix_whiteboard_nodes_entry", "whiteboard_nodes (entry_id)"),
        ("ix_whiteboard_nodes_board", "whiteboard_nodes (board_id)"),
        ("ix_whiteboard_sketches_board", "whiteboard_sketches (board_id)"),
        ("ix_reminders_entry", "reminders (entry_id)"),
        ("ix_entry_bookmarks_entry", "entry_bookmarks (entry_id)"),
        # The last five foreign keys with no index leading on them (the
        # Brief 60 census, WORLD_CLASS_PLAN 26.4): deleting an entry, an
        # entity, a document or a bookmark scanned these join tables.
        ("ix_entry_bookmarks_bookmark", "entry_bookmarks (bookmark_id)"),
        ("ix_document_bookmarks_document", "document_bookmarks (document_id)"),
        ("ix_document_bookmarks_bookmark", "document_bookmarks (bookmark_id)"),
        ("ix_entity_mentions_entry", "entity_mentions (entry_id)"),
        ("ix_entity_mentions_entity", "entity_mentions (entity_id)"),
        # **Partial indexes over the rare live flags** (L-world-class-21, the
        # census of WORLD_CLASS_PLAN 26.4: `entries.is_private` x54 and
        # `is_board` x37 had no index leading on them). The flags are
        # low-cardinality, so an index per flag is the wrong shape, and the
        # first cut (`(is_private, is_board) WHERE is_deleted = 0`) was worse
        # than none: SQLite took `is_private = 0` for a selective equality and
        # put a sort on /timeline and on "every live note by id". What is
        # worth an index is the *rare* value, held alone: the live private
        # notes and the live boards, in id order. Planned at 5,000 notes,
        # "live private" and "live boards" went from `SCAN entries` to a
        # covering index read of just those rows. The common value
        # (`is_private = 0`) stays a table read on purpose: it is nearly every
        # row. `tests/test_indexes_at_5000.py` pins both halves.
        ("ix_entries_live_private", "entries (id) WHERE is_deleted = 0 AND is_private = 1"),
        ("ix_entries_live_boards", "entries (id) WHERE is_deleted = 0 AND is_board = 1"),
        # **The all-spaces orders** (WORLD_CLASS_PLAN 19.3, the whole
        # `EXPLAIN QUERY PLAN` pass, 2026-10-05: scratchpad/
        # plat1005_query_plans.py over every GET route at 5,000 notes). Every
        # composite above leads with `workspace_id`, and they were measured
        # with one space selected. The page's default is "All spaces", which
        # sends no equality on `workspace_id` (`_add_workspace_filter` adds
        # nothing, or a NOT IN for hidden spaces), so not one of them could
        # serve an ORDER BY in the view most people are in: SQLite sorted.
        #
        # **Keyed by the ORDER BY alone, not by `is_deleted` first.** The
        # first cut put `is_deleted` in front, the way the scoped ones are
        # built, and measured worse elsewhere: with no `ANALYZE` statistics
        # SQLite takes an equality on an indexed column as selective, so
        # every "live notes, by id" scan (duplicates 69.6 to 98.1 ms, a
        # note's connections 31.9 to 40.0) switched from reading the table
        # in rowid order to an index lookup plus a sort. An index on the
        # order alone is only chosen where it removes a sort; the filters are
        # checked on the walk, and the rows they drop are few (the bin and
        # the archive are a few percent of a notebook). Before and after,
        # each statement alone, at 5,000 notes:
        # the notes list's first page, the Library and link suggestions
        # (24.98 ms, "USE TEMP B-TREE FOR ORDER BY");
        ("ix_entries_order_all", "entries (pinned DESC, created_at DESC, id DESC)"),
        # the bin and the archive (5.10 and 4.12 ms, sorting). **Partial**,
        # holding only binned or archived rows, and that is load-bearing: a
        # whole-table index on `archived_at` was taken by the notes list's
        # `archived_at IS NULL` as an equality lookup (SQLite plans `IS NULL`
        # like `= ?`), which put the sort back on the main list (40.2 ms);
        # one only the bin's and the archive's own WHERE can match cannot be.
        ("ix_entries_deleted_order", "entries (deleted_at DESC, id DESC) WHERE is_deleted = 1"),
        ("ix_entries_archived_order", "entries (archived_at DESC, id DESC) WHERE archived_at IS NOT NULL"),
        # the Timeline's page and the Dashboard's counts since a date (35.79
        # and 15.15 ms, a range on `created_at` read by scanning every note);
        ("ix_entries_created_order", "entries (created_at DESC, id DESC)"),
        # the Library's activity rows, newest first over the whole event log
        # (76.62 ms at 20,000 events, "SCAN audit_log" and a sort), and the
        # lookups by action (corrections, the link-reason backfill);
        ("ix_audit_log_recent", "audit_log (created_at DESC, id DESC)"),
        ("ix_audit_log_action", "audit_log (action, id DESC)"),
        # and the other lists' pages: uploads (5.52 ms at 5,000), documents
        # (5.08 ms at 1,000), chats and reminders.
        ("ix_media_uploads_order", "media_uploads (created_at DESC, id DESC)"),
        ("ix_documents_order", "documents (updated_at DESC, id DESC)"),
        # the Timeline's documents since a date (13.38 ms at 1,000) and the
        # Dashboard's most-opened notes (7.17 ms, sorting every live note);
        ("ix_documents_created_order", "documents (created_at DESC, id DESC)"),
        ("ix_entries_accessed_order", "entries (access_count DESC, id DESC)"),
        ("ix_conversations_order", "conversations (pinned DESC, updated_at DESC, id DESC)"),
        ("ix_reminders_due_order", "reminders (due_at, id)"),
        # The chat list in one space: `pinned DESC, updated_at DESC, id DESC`
        # over the unarchived, which `(workspace_id, updated_at DESC)` above
        # never matched (audit 2026-10-05, ARCH-05); the all-spaces shape is
        # `ix_conversations_order`.
        (
            "ix_conversations_live_pinned",
            "conversations (workspace_id, archived_at, pinned DESC, updated_at DESC, id DESC)",
        ),
    )

    #: Unique indexes, partial where the column is optional: the same
    #: additive `IF NOT EXISTS` convention as `_INDEXES`.
    _UNIQUE_INDEXES: tuple[tuple[str, str], ...] = (
        ("uq_entries_client_key", "entries (client_key) WHERE client_key IS NOT NULL"),
    )

    def _ensure_readings_view(self) -> None:
        """Every reading of a file as one `readings` view (F10, `core/readings.py`).

        Replaced when its definition changes, so a column added to it reaches
        a notebook made before; a failure is logged and the app starts, since
        nothing writes through the view and only the readings route reads it.
        """
        from tessellate.core import readings

        try:
            with self.engine.begin() as connection:
                readings.ensure_view(connection)
        except Exception:  # noqa: BLE001  # a read model must never stop the app opening
            logging.getLogger("tessellate.db").warning("could not create the readings view", exc_info=True)

    def _ensure_indexes(self) -> None:
        """Create the composite indexes the hot list queries need.

        `IF NOT EXISTS` throughout, run on every startup, the same additive
        convention `_ensure_fts5` and `_add_missing_columns` already use, and
        for the same reason: it has to be correct on a database created by any
        earlier version, not only on a fresh one.

        Adding an index is not free, every write to `entries` maintains it , 
        but these are read-heavy paths by a wide margin in a notebook app, and
        the alternative measured on a 20k-note database was a temp B-tree sort
        of the whole table per request.
        """
        with self.engine.begin() as connection:
            for name, definition in self._INDEXES:
                connection.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS {name} ON {definition}"
                )
            for name, definition in self._UNIQUE_INDEXES:
                connection.exec_driver_sql(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {definition}"
                )

    #: Rows whose space has to be *inherited* rather than defaulted, as
    #: `(table, parent-id column, parent table)`. See
    #: `_backfill_inherited_workspaces` for why a plain DEFAULT is wrong here.
    _WORKSPACE_INHERITANCE = (
        ("attachments", "entry_id", "entries"),
        ("reminders", "entry_id", "entries"),
        ("whiteboard_nodes", "board_id", "entries"),
        ("whiteboard_sketches", "board_id", "entries"),
        ("whiteboard_objects", "board_id", "entries"),
    )
