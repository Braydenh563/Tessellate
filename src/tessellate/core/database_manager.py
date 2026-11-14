"""The database manager: engine setup, the Alembic baseline and upgrade, and the additive in-place migrations.

Moved whole out of `core/database.py` (audit K24, BK11), unchanged. It sits above
the models: it builds the engine, runs the migrations and hands out sessions, so
`core/database.py` never imports it back. Callers import `DatabaseManager` from here.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import zlib
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from tessellate.core import concurrency
from tessellate.core.database_indexes import IndexesMixin
from tessellate.core.database import Base, Space


_logger = logging.getLogger("tessellate.database")


def _migrations_root() -> Path:
    """Where `alembic.ini` and `migrations/` live, source or frozen.

    Mirrors `api/app.py`'s own `FRONTEND_DIR` resolution exactly: same
    directory depth from this file (`src/tessellate/core/database.py`) to
    the repo root, same `sys.frozen`/`_MEIPASS` split for a PyInstaller
    build. Kept here rather than imported from `app.py` because `core/` is
    the bottom layer (`deps.register_cache_reset`'s own docstring, above,
    already explains why that direction matters in this codebase).
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]


def _safety_copy_before_migrating(cfg, current: str, db_path: Path) -> None:  # noqa: ANN001
    """A copy of the database before a pending migration runs (audit
    2026-10-10, item 8). A launcher update that pulls a migration used to run
    it on the only copy of the notebook, with the nightly backup up to a day
    old. Only when the stamped revision is behind head: an ordinary launch
    changes nothing and copies nothing. A failed copy is logged and the
    migration still runs, because this must never be what stops the app
    starting (the caller's own rule)."""
    from alembic.script import ScriptDirectory

    try:
        if current == ScriptDirectory.from_config(cfg).get_current_head():
            return
        from tessellate.core import backup

        backup.backup_now(db_path, db_path.parent, origin="update")
    except Exception:  # noqa: BLE001
        _logger.warning("Could not take a safety copy before migrating", exc_info=True)


def _ensure_alembic_baseline(db_path: Path) -> None:
    """Make Alembic aware of this exact database, without ever running DDL
    against one that doesn't need it.

    Every database this app opens already has the correct current schema by
    the time this runs, `create_all()` and `_add_missing_columns()` above
    guarantee that, unchanged, for both a brand-new database and an existing
    one missing a column. What Alembic adds is only for the day a *rename*
    or *drop* is actually needed, which those two never could do (`core/
    database.py`'s own module docstring has said so from the start). So:

    - No `alembic_version` table yet (every database before this function
      existed, plus every fresh one `create_all()` just built) → **stamp**
      to the baseline revision. Stamping records "this database is already
      at revision X" without executing revision X's `upgrade()`, correct
      here specifically because the schema already matches it by
      construction, not because stamping is generally safe to reach for.
    - `alembic_version` already exists → a previous startup already
      stamped or migrated this database, so **upgrade** to head. A no-op
      when nothing newer than what's stamped has been added; applies any
      real migration that has, the actual point of wiring this in at all.

    Never allowed to stop the app from starting: this is new, additive
    infrastructure layered on a schema mechanism that already works on its
    own, not a replacement for it. Any failure here: a packaging issue in
    a frozen build that didn't bundle `migrations/` correctly, a locked
    file, anything: is logged and swallowed rather than raised.

    `DatabaseManager.__init__` skips calling this at all under pytest
    (`PYTEST_CURRENT_TEST`, which pytest itself sets, no per-test opt-in
    needed): a throwaway `tmp_path` database that gets discarded the
    moment its one test ends has nothing to gain from being stamped, and
    this measured ~30ms per call against a suite where `DatabaseManager`
    runs in a large fraction of the ~1,600 tests: real minutes, for a
    database that will never see a second startup to make the "upgrade"
    half of this function's job matter. The skip lives at the call site,
    not in here, so `tests/test_alembic_baseline.py` can call this function
    directly and actually exercise it.
    """
    try:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine as _create_engine

        root = _migrations_root()
        ini_path = root / "alembic.ini"
        if not ini_path.is_file():
            _logger.warning("Alembic config not found at %s, skipping", ini_path)
            return

        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(root / "migrations"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        # alembic.ini's own [loggers] section defaults to INFO, meant for a
        # human watching a terminal run `alembic upgrade head` by hand: not
        # for every one of this app's own startups. This runs silently
        # unless something actually goes wrong (the except below still logs).
        logging.getLogger("alembic").setLevel(logging.WARNING)

        probe_engine = _create_engine(f"sqlite:///{db_path}")
        try:
            with probe_engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
        finally:
            probe_engine.dispose()

        # migrations/env.py calls logging.config.fileConfig() every time
        # command.stamp/upgrade below runs it, and that call unconditionally
        # REPLACES the handler list (and resets the level) of every logger
        # alembic.ini explicitly configures, root among them, regardless
        # of disable_existing_loggers, which only protects loggers *not*
        # listed there from being disabled. alembic.ini's own
        # [logger_root] sets handlers = console, so this silently tore
        # logbuffer.install()'s own handler off the root logger and
        # replaced it with Alembic's plain console handler for the rest of
        # this process's life: reported directly: the Settings -> Logs
        # viewer showed nothing but Alembic's own plugin-registration
        # lines, forever, because nothing the app itself logs reaches a
        # handler that no longer exists. Same mechanism undid the
        # WARNING level just set above ([logger_alembic] says INFO),
        # which is why those plugin lines were visible at all. Restored
        # here rather than in env.py itself, because a human running
        # `alembic upgrade head` directly from a terminal *wants*
        # fileConfig()'s effect to stick for that short-lived process, 
        # this restore only matters for the in-process caller, which is
        # this function.
        root_logger = logging.getLogger()
        saved_root_handlers = list(root_logger.handlers)
        saved_root_level = root_logger.level
        saved_alembic_level = logging.getLogger("alembic").level
        try:
            if current is None:
                command.stamp(cfg, "head")
            else:
                _safety_copy_before_migrating(cfg, current, db_path)
                command.upgrade(cfg, "head")
        finally:
            root_logger.handlers = saved_root_handlers
            root_logger.setLevel(saved_root_level)
            logging.getLogger("alembic").setLevel(saved_alembic_level)
    except Exception:  # noqa: BLE001  # see docstring: never fatal to startup
        _logger.warning("Alembic baseline/upgrade step failed", exc_info=True)


class DatabaseManager(IndexesMixin):
    """Owns the one engine + session factory for the whole app."""

    def __init__(self, db_path: Path) -> None:
        # check_same_thread=False because FastAPI serves requests from a
        # threadpool; SQLAlchemy still gives each request its own session.
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            pool_size=concurrency.POOL_SIZE,
            max_overflow=concurrency.POOL_OVERFLOW,
            pool_timeout=concurrency.POOL_TIMEOUT,
        )

        # Per-connection SQLite settings. All of these are per-connection
        # rather than per-database, so they have to be set on every connect.
        @event.listens_for(self.engine, "connect")
        def _configure_connection(dbapi_connection, _record):  # noqa: ANN001
            # SQLite ignores foreign keys unless told otherwise.
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            # WAL lets readers carry on while a write is in progress. Without
            # it, saving a note blocks every concurrent read, and FastAPI
            # serves from a threadpool, so a background job (the janitor, an
            # embedding write) overlapping a page load is routine rather than
            # rare. WAL persists on the file, but setting it per connection is
            # harmless and covers a database created by an older version.
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            # When two writers do collide, wait rather than failing instantly.
            # The default is 0, which turns a millisecond of contention into a
            # "database is locked" error the user sees as a broken save.
            dbapi_connection.execute("PRAGMA busy_timeout=5000")
            # NORMAL is the recommended durability level under WAL: still
            # crash-safe, without an fsync on every single commit.
            dbapi_connection.execute("PRAGMA synchronous=NORMAL")
            # Temp b-tree sorts and the transient tables ANALYZE/vacuum use
            # otherwise spill to a file under the data directory, the same
            # disk this app is trying to keep quiet while a local model reads
            # its own weights off it. The working set here is one user's own
            # notebook, not a multi-gigabyte warehouse query, so keeping it in
            # RAM instead costs nothing that matters (PLAN.md §0 P5).
            dbapi_connection.execute("PRAGMA temp_store=MEMORY")

        Base.metadata.create_all(self.engine)  # creates missing tables only
        #: A start that finds the schema as the last one stamped it has no column to add
        #: (audit 1028 K35): the scan is one `PRAGMA table_info` per table.
        stamped = self._schema_is_stamped()
        if not stamped:
            self._add_missing_columns()
        self._rebuild_categories_unique_constraint()
        if not stamped:
            self._stamp_schema()
        self._backfill_inherited_workspaces()
        self._drop_orphan_links()
        self._ensure_fts5()
        self._ensure_indexes()
        self._ensure_readings_view()
        # See _ensure_alembic_baseline's own docstring for why this is
        # skipped under pytest: a throwaway per-test database has nothing
        # to gain from being stamped, and the constructor runs in most of
        # this suite's ~1,600 tests.
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            _ensure_alembic_baseline(db_path)
        self._session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._ensure_search_index()
        self._ensure_default_spaces()

    def _ensure_search_index(self) -> None:
        """The index that covers every kind (`search/index.py`), built once.

        Below the session factory rather than beside `_ensure_fts5` because a
        database that has never had this table has to be *filled*, and filling
        it needs a session.

        `importlib`, not an `import` statement: `search/index.py` reads this
        module's models, so naming it here closes `core.database ->
        search.index -> core.database`, and the storage layer is the wrong
        end of that edge to be doing the naming.
        `tests/test_no_import_cycles.py` counts the statement wherever it
        sits (CodeQL does), so a function-level `from ... import` would hide
        the cycle rather than break it.
        """
        search_index = importlib.import_module("tessellate.search.index")

        with self.engine.begin() as connection:
            created = search_index.ensure_table(connection)
        if not created:
            # A table from before maps had their own kind, or before a
            # board's row held the words on it: a diff over the boards, a
            # read-only no-op once it has run (`reconcile_boards`).
            with self.session() as session:
                # Either may write; `or` would skip the second once the first did.
                boards = search_index.reconcile_boards(session)
                late = search_index.reconcile_sources(session)
                private_files = search_index.reconcile_private_files(session)
                note_files = search_index.reconcile_note_files(session)
                if boards or late or private_files or note_files:
                    session.commit()
            return
        # Only on the one startup that creates the table: every write after
        # this keeps itself in step (see the module's `after_flush` hook), so
        # this is a migration, not a recurring cost.
        with self.session() as session:
            search_index.rebuild(session)
            session.commit()

    def _ensure_default_spaces(self) -> None:
        """Seed default spaces if none exist."""
        with self.session() as session:
            if session.query(Space).first() is None:
                defaults = [
                    Space(id="default", name="Default space", icon="ph-house"),
                    Space(id="work", name="Work", icon="ph-briefcase"),
                    Space(id="personal", name="Personal", icon="ph-user"),
                    Space(id="projects", name="Projects", icon="ph-kanban")
                ]
                session.add_all(defaults)
                session.commit()

    def _rebuild_categories_unique_constraint(self) -> None:
        """Move `categories.name`'s UNIQUE from the column to (space, name).

        `create_all` never touches an existing table and `_add_missing_columns`
        only ever *adds* columns, so an existing database keeps whatever
        constraints it was built with, and the one this replaces made a
        second space unusable. `get_or_create_category` looks a name up under
        the current space's filter; in another space it finds nothing, tries
        to insert, and hits a UNIQUE that spans every space at once.
        Reproduced as a **500 on `POST /entries`** the first time a note in a
        new space wanted a category name the default space already had, 
        which for ordinary names ("Work", "Ideas", "Uni") is immediately.

        SQLite cannot drop a constraint, so this is the standard rebuild:
        make the table with the right shape, copy every row, swap the names.
        Guarded on actually finding the old single-column unique index, so it
        runs exactly once per database and is a no-op on a fresh one (where
        `create_all` has already built the correct shape) and on every
        startup after the first.

        Never allowed to stop the app from starting, the same rule
        `_ensure_alembic_baseline` follows: a database that somehow cannot be
        rebuilt still opens, with the old constraint and the old limitation,
        rather than not opening at all.
        """
        try:
            with self.engine.begin() as connection:
                tables = {
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "categories" not in tables:
                    return
                stale = None
                for index in connection.exec_driver_sql(
                    "PRAGMA index_list('categories')"
                ).fetchall():
                    name, unique = index[1], index[2]
                    if not unique:
                        continue
                    columns = [
                        row[2]
                        for row in connection.exec_driver_sql(
                            f"PRAGMA index_info('{name}')"
                        ).fetchall()
                    ]
                    if columns == ["name"]:
                        stale = name
                        break
                if stale is None:
                    return  # already the composite constraint, or never had one

                _logger.info("rebuilding categories to scope its unique name per space")
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.exec_driver_sql(
                    'CREATE TABLE "categories_rebuilt" ('
                    " id INTEGER NOT NULL PRIMARY KEY,"
                    " name VARCHAR(100) NOT NULL,"
                    " description TEXT,"
                    " colour VARCHAR(16),"
                    " created_at DATETIME,"
                    " workspace_id VARCHAR DEFAULT 'default' NOT NULL,"
                    " CONSTRAINT uq_categories_workspace_name UNIQUE (workspace_id, name)"
                    ")"
                )
                connection.exec_driver_sql(
                    'INSERT INTO "categories_rebuilt" '
                    " (id, name, description, colour, created_at, workspace_id)"
                    " SELECT id, name, description, colour, created_at,"
                    "        COALESCE(workspace_id, 'default') FROM categories"
                )
                connection.exec_driver_sql('DROP TABLE "categories"')
                connection.exec_driver_sql(
                    'ALTER TABLE "categories_rebuilt" RENAME TO "categories"'
                )
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_categories_workspace_id"
                    " ON categories (workspace_id)"
                )
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        except Exception:
            _logger.warning(
                "couldn't rebuild the categories table; spaces will still share "
                "one category namespace on this database",
                exc_info=True,
            )

    def _backfill_inherited_workspaces(self) -> None:
        """Give a newly-scoped child row the space its parent note is in.

        These six tables (the five here plus `media_uploads`) had no
        `workspace_id` at all until this ran, which is why an image uploaded
        inside a class-specific space showed up in the main space's gallery
        and a reminder written in one space appeared in every other, 
        reported directly, and reproduced before this was written.

        Adding the column is the easy half. `_add_missing_columns` backfills
        it with the model default, `'default'`, and for a *parentless* row
        (a `media_uploads` row, a whiteboard object on the shared
        board_id-NULL board) that is the honest answer: it really was
        visible everywhere before, and the main space is where it belongs
        now.

        For a row that hangs off a note it is actively wrong. An attachment
        on a note in space `uni` stamped `'default'` does not merely land in
        the wrong gallery: the workspace loader criteria then filter it out
        of its *own note*, so a user in `uni` opens the note they attached it
        to and the file is gone. That is data loss as far as anyone using it
        can tell. So each of these inherits from its parent note instead,
        and only a row with no parent keeps the default.

        Idempotent by construction: it only touches rows still sitting at
        `'default'` whose parent says otherwise, so a second startup is a
        no-op, and a row a user has deliberately moved is never dragged back.
        """
        with self.engine.begin() as connection:
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "entries" not in tables:
                return
            for table, fk, parent in self._WORKSPACE_INHERITANCE:
                if table not in tables:
                    continue
                #: The model's columns, not a `PRAGMA table_info` per table (audit 1028 K35):
                #: `_add_missing_columns` has run, so a table the model knows has them all.
                model = Base.metadata.tables.get(table)
                columns = set(model.columns.keys()) if model is not None else set()
                if "workspace_id" not in columns or fk not in columns:
                    continue
                connection.exec_driver_sql(
                    f'UPDATE "{table}" SET workspace_id = ('
                    f'  SELECT p.workspace_id FROM "{parent}" p WHERE p.id = "{table}".{fk}'
                    f") WHERE {fk} IS NOT NULL AND workspace_id = 'default'"
                    f'   AND EXISTS (SELECT 1 FROM "{parent}" p WHERE p.id = "{table}".{fk}'
                    f"              AND p.workspace_id <> 'default')"
                )

    def _drop_orphan_links(self) -> None:
        """Remove link rows whose source or target note no longer exists.

        Every purge clears a note's links (`manager_purge._hard_delete`), so a row
        pointing at a missing note came from a path that did not (a database
        written with foreign keys off, an interrupted import). Left in place
        it inflates the link count (diagnostics showed 4,234 links on 37
        notes) and every walk of the link table. Idempotent: a clean table
        matches nothing. A note in the bin still exists, so its links stay.
        """
        with self.engine.begin() as connection:
            tables = {
                row[0]
                for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if not {"entries", "entry_links"} <= tables:
                return
            connection.exec_driver_sql(
                "DELETE FROM entry_links WHERE source_entry_id NOT IN (SELECT id FROM entries)"
                " OR target_entry_id NOT IN (SELECT id FROM entries)"
            )

    @staticmethod
    def _model_signature() -> str:
        """Every model table's column names and types, in a fixed order."""
        return ";".join(
            f"{table.name}({','.join(f'{column.name} {column.type}' for column in table.columns)})"
            for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name)
        )

    def _schema_stamp(self) -> int:
        """A 31-bit fingerprint of the model and of the model's tables as SQLite
        holds them (their CREATE text, which an added or dropped column changes).
        Only the model's tables: the search and full-text tables other steps make
        after this one would otherwise change it between two starts."""
        names = sorted(Base.metadata.tables)
        marks = ",".join("?" for _ in names)
        with self.engine.connect() as connection:
            held = connection.exec_driver_sql(
                f"SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ({marks}) ORDER BY name",
                tuple(names),
            ).fetchall()
        text = self._model_signature() + "|" + "|".join(f"{name}:{sql}" for name, sql in held)
        return zlib.crc32(text.encode("utf-8")) & 0x7FFFFFFF

    def _schema_is_stamped(self) -> bool:
        with self.engine.connect() as connection:
            stored = connection.exec_driver_sql("PRAGMA user_version").scalar()
        return stored == self._schema_stamp()

    def _stamp_schema(self) -> None:
        """Record the fingerprint, after the steps that can change the tables ran."""
        stamp = self._schema_stamp()
        with self.engine.begin() as connection:
            connection.exec_driver_sql(f"PRAGMA user_version = {int(stamp)}")

    def _add_missing_columns(self) -> None:
        """Additive auto-migration for existing databases.

        create_all() never touches tables that already exist, so a
        database made by an older version lacks newly added columns and
        every query on that table would 500. Add them here instead of
        making the user delete their data."""
        with self.engine.begin() as connection:
            for table in Base.metadata.tables.values():
                rows = connection.exec_driver_sql(
                    f'PRAGMA table_info("{table.name}")'
                ).fetchall()
                if not rows:
                    continue  # brand-new table: create_all just made it
                existing = {row[1] for row in rows}
                for column in table.columns:
                    if column.name in existing:
                        continue
                    ddl = (
                        f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" '
                        f"{column.type.compile(self.engine.dialect)}"
                    )
                    # Backfill old rows with the model's default when it's a
                    # plain value (callables like utcnow can't run in DDL, 
                    # those columns stay NULL for pre-existing rows).
                    if column.default is not None and column.default.is_scalar:
                        value = column.default.arg
                        if isinstance(value, bool):
                            value = int(value)
                        if isinstance(value, str):
                            # A quote in the default doubled (audit 1028 K21):
                            # left as it was, one apostrophe broke every start.
                            quoted = value.replace("'", "''")
                            ddl += f" DEFAULT '{quoted}'"
                        else:
                            ddl += f" DEFAULT {value}"
                    connection.exec_driver_sql(ddl)

    def optimize(self) -> None:
        """`PRAGMA optimize` at a clean quit (audit 1028 K37), as SQLite advises:
        it gathers the statistics the planner lacks, only for tables the
        launch's queries used, so plans keep up as a notebook grows.

        Then the write-ahead log is folded into the file and emptied. A
        seeded notebook measured 4 KB of file beside 2.2 MB of log after a
        clean quit, so deleting the `-wal` lost every note (INBOX 1573)."""
        try:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA optimize")
                connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:  # noqa: BLE001  # a quit must not fail over statistics
            logging.getLogger(__name__).info("PRAGMA optimize skipped: %s", exc)

    def session(self) -> Session:
        """A fresh session; caller is responsible for closing it."""
        return self._session_factory()
