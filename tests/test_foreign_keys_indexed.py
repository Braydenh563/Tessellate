"""Every foreign key has an index leading on its column (WORLD_CLASS_PLAN 26.4).

With `foreign_keys=ON`, deleting a parent row looks up the child rows by the
foreign key column; unindexed, that is a table scan per deleted row (604 ms
against 2.9 ms on 5,000 notes). The Brief 60 census found five join-table
columns without one; this holds the count at zero on a fresh database.
"""

from __future__ import annotations

from tessellate.core.database_manager import DatabaseManager


def _unindexed(connection) -> list[str]:
    tables = [r[0] for r in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")]
    missing = []
    for table in tables:
        if table.startswith(("sqlite_", "alembic_")) or "_fts" in table:
            continue
        leading = set()
        for index in connection.exec_driver_sql(f'PRAGMA index_list("{table}")').fetchall():
            first = connection.exec_driver_sql(f'PRAGMA index_info("{index[1]}")').fetchall()
            if first:
                leading.add(first[0][2])
        pk = [r[1] for r in connection.exec_driver_sql(f'PRAGMA table_info("{table}")') if r[5] == 1]
        if len(pk) == 1:
            leading.add(pk[0])
        for fk in connection.exec_driver_sql(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk[3] not in leading:
                missing.append(f"{table}.{fk[3]}")
    return sorted(missing)


def test_no_foreign_key_is_without_a_leading_index(tmp_path):
    with DatabaseManager(tmp_path / "fk.db").engine.connect() as connection:
        missing = _unindexed(connection)
    assert not missing, f"foreign keys with no index leading on the column: {missing}"
