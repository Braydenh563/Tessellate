"""Boot-route statements that read by a column expression are planned off an index (L-world-class-125).

The pass of 2026-11-14 (`scratchpad/plat1005_query_plans.py 5000`: 156 routes,
324 distinct SELECTs) left 158 plan lines with a SCAN. Almost all are reads of
every live note by design (the graph, duplicates, tidy, statistics: 3 to 69 ms
at 5,000). The one that was a scan only because of how it was written is the
dashboard line's count of today's and yesterday's notes, `date(created_at) IN
(...)`, which cannot use an index; it now also bounds `created_at`.

SQLite plans without statistics, so a few notes are enough.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import event

from tessellate.core import deps
from tessellate.core.database import Entry
from tests._clock import SUITE_NOW, pin_clock


def test_todays_line_counts_its_two_days_from_the_created_at_index(client, monkeypatch):
    pin_clock(monkeypatch, SUITE_NOW)
    session = deps.get_db().session()
    try:
        now = SUITE_NOW.replace(tzinfo=None)
        session.add_all([Entry(content=f"Note {i}", created_at=now - timedelta(days=i)) for i in range(6)])
        session.commit()
    finally:
        session.close()
    seen: list[tuple[str, tuple]] = []

    def before(_conn, _cursor, statement, parameters, _context, _many):
        if "date(entries.created_at)" in statement and "count(*)" in statement:
            seen.append((statement, parameters))

    engine = deps.get_db().engine
    event.listen(engine, "before_cursor_execute", before)
    try:
        assert client.get("/insights/today-line").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", before)
    assert len(seen) == 1
    raw = engine.raw_connection()
    try:
        plan = [r[-1] for r in raw.cursor().execute("EXPLAIN QUERY PLAN " + seen[0][0], seen[0][1]).fetchall()]
    finally:
        raw.close()
    assert not any(step.startswith("SCAN entries") and "INDEX" not in step for step in plan), plan
    assert any("ix_entries_created_order" in step for step in plan), plan
