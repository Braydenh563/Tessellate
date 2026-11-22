"""Foreign-key and filtered-column lookups are index searches at 5,000 notes (L569, L-world-class-21).

SQLite plans without statistics, so the plan does not depend on the row count,
but the notebook here is the size the plan's census measured.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tessellate.core.database import AuditLog, Entry
from tessellate.core.database_manager import DatabaseManager

#: Child-table lookups a parent delete (or a note's own page) performs.
FK_LOOKUPS = [
    "SELECT 1 FROM entity_mentions WHERE entry_id = 5",
    "SELECT 1 FROM entity_mentions WHERE entity_id = 5",
    "SELECT 1 FROM document_bookmarks WHERE document_id = 5",
    "SELECT 1 FROM document_bookmarks WHERE bookmark_id = 5",
    "SELECT 1 FROM entry_bookmarks WHERE entry_id = 5",
    "SELECT 1 FROM entry_bookmarks WHERE bookmark_id = 5",
    "SELECT 1 FROM entries WHERE parent_id = 5",
    "SELECT 1 FROM reminders WHERE entry_id = 5",
    "SELECT 1 FROM whiteboard_nodes WHERE board_id = 5",
    "SELECT 1 FROM audit_log WHERE entity_id = 5",
]


#: Filtered-column reads of the rare flag values on live notes (the flags have
#: no index of their own: low cardinality, so only the rare value is indexed).
FILTERED = [
    "SELECT id FROM entries WHERE is_deleted = 0 AND is_board = 1",
    "SELECT id FROM entries WHERE is_deleted = 0 AND is_private = 1",
    "SELECT count(*) FROM entries WHERE is_deleted = 0 AND is_private = 1",
]

#: The trap `database_indexes` documents: an index on a flag must not turn a
#: read of every live note into an index lookup plus a sort.
STILL_TABLE_READS = [
    "SELECT * FROM entries WHERE is_deleted = 0 ORDER BY id",
    "SELECT * FROM entries WHERE is_deleted = 0 AND archived_at IS NULL ORDER BY id",
]


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> DatabaseManager:
    database = DatabaseManager(tmp_path_factory.mktemp("idx") / "idx.db")
    with database.session() as session:
        session.info["workspace_id"] = "default"
        session.add_all(
            Entry(
                content=f"note {i}",
                workspace_id="default",
                is_deleted=(i % 50 == 0),
                is_private=(i % 7 == 0),
                is_board=(i % 40 == 0),
            )
            for i in range(5000)
        )
        session.add_all(AuditLog(action="edited", entity_type="entry", entity_id=i + 1) for i in range(5000))
        session.commit()
    return database


def _plan(db: DatabaseManager, sql: str) -> str:
    with db.engine.connect() as connection:
        return " | ".join(row[-1] for row in connection.execute(text("EXPLAIN QUERY PLAN " + sql)))


@pytest.mark.parametrize("sql", FK_LOOKUPS)
def test_foreign_key_lookup_is_an_index_read_not_a_table_scan(db, sql):
    plan = _plan(db, sql)
    for step in plan.split(" | "):
        assert not (step.startswith("SCAN") and "USING" not in step), plan


@pytest.mark.parametrize("sql", FILTERED)
def test_a_flag_filter_on_live_notes_is_an_index_read(db, sql):
    plan = _plan(db, sql)
    assert "ix_entries_live_private" in plan or "ix_entries_live_boards" in plan, plan


@pytest.mark.parametrize("sql", STILL_TABLE_READS)
def test_the_partial_indexes_do_not_sort_a_read_of_every_live_note(db, sql):
    plan = _plan(db, sql)
    assert "TEMP B-TREE" not in plan and "ix_entries_live_" not in plan, plan
