"""L472: a reminder ticked before `done_at` existed is dated on the next start,
so the review's "done" count (`review_digest._counts`) sees it."""

from __future__ import annotations

from sqlalchemy import text

from tessellate.core.database_manager import DatabaseManager


def _rows(db):
    with db.engine.connect() as c:
        return dict(c.execute(text("SELECT text, done_at FROM reminders")).fetchall())


def test_old_done_reminders_get_a_done_at_and_open_ones_stay_empty(tmp_path):
    path = tmp_path / "m.db"
    db = DatabaseManager(path)
    with db.engine.begin() as c:
        for name, done, done_at in (("old done", 1, None), ("open", 0, None), ("stamped", 1, "2026-01-05 08:00:00.000000")):
            c.execute(
                text("INSERT INTO reminders (text, due_at, done, done_at, created_at, recurring, priority, workspace_id) "
                     "VALUES (:t, '2026-03-02 09:00:00', :d, :a, '2026-03-01 09:00:00', 'none', 'normal', 'default')"),
                {"t": name, "d": done, "a": done_at},
            )
    db.engine.dispose()
    again = DatabaseManager(path)  # the next start
    rows = _rows(again)
    assert str(rows["old done"]).startswith("2026-03-02")
    assert rows["open"] is None
    assert str(rows["stamped"]).startswith("2026-01-05")
    again.engine.dispose()
    assert str(_rows(DatabaseManager(path))["old done"]).startswith("2026-03-02")  # idempotent
