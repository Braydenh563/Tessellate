"""The perf budget at 2,000 notes (audit 1031 PF7, GR1; ranked row 52).

`test_perf_budget.py` holds the first-click routes at 300 notes. The audit
measured the list, search and boot routes at 545 and only the graph and
`/statistics` at 2,000, so a route that is fine at 300 and quadratic at 2,000
had no gate. Same numbers per route as there, plus the response size: statements (exact,
any machine), best-of-three wall time (generous, for a loaded runner) and the
bytes sent (what a phone pays for the list).

The notebook is built on a fixed clock: every note is dated from `BASE` by
its number, so the date-bound routes (statistics, the graph's time view, the
journal) read the same rows on every run. The wall time is the one thing
that is measured, not set.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from tessellate.core import deps
from tessellate.entry import manager

NOTES = 2000
BASE = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
TOPICS = ["garden", "boiler", "rent", "project", "trip", "recipe", "invoice", "reading"]

#: route: (statements, seconds, response bytes). Measured at 2,000 notes on
#: this fixture, 2026-11-01 (statements, ms, bytes in each comment); the
#: statement and byte budgets carry a little room, the seconds carry a loaded
#: runner. Raising one needs a reason in its comment, like the gzip caps.
BUDGET = {
    "/entries?limit=60": (12, 2.0, 60_000),  # 9, 14 ms, 48 KB
    "/entries?limit=200": (12, 3.0, 200_000),  # 9, 33 ms, 162 KB (the audit read 210 ms at 545 notes on a cold disk)
    "/library": (25, 3.0, 135_000),  # 22, 33 ms, 107 KB
    "/graph": (14, 4.0, 1_150_000),  # 12, 36 ms, 937 KB
    "/search?q=boiler": (9, 3.0, 9_000),  # 6, 16 ms, 7 KB
    "/search?q=garden+trip": (12, 3.0, 9_000),  # 9, 17 ms, 7 KB
    "/insights/stats": (8, 2.0, 1_000),  # 5, 13 ms
    "/statistics": (22, 3.0, 2_000),  # 18, 26 ms
    "/categories": (5, 1.5, 1_000),  # 3, 10 ms
    "/tags": (5, 1.5, 1_000),  # 3, 8 ms
    "/export/json": (11, 5.0, 1_000_000),  # 8, 64 ms, 811 KB
}


def _build(session) -> None:
    for n in range(NOTES):
        topic = TOPICS[n % len(TOPICS)]
        manager.create_entry(
            session,
            f"Note {n} about the {topic} and the {TOPICS[(n * 3) % len(TOPICS)]}, tagged #t{n % 11}.",
            category_name=["Home", "Work", "Garden", "Money"][n % 4],
            tags=[f"t{n % 11}"],
        )
    session.commit()
    # The fixed clock: one statement dates every note from `BASE` by its id.
    rows = session.execute(text("SELECT id FROM entries ORDER BY id")).scalars().all()
    for index, entry_id in enumerate(rows):
        stamp = (BASE + timedelta(hours=6 * index)).replace(tzinfo=None).isoformat(sep=" ")
        session.execute(
            text("UPDATE entries SET created_at = :at, edited_at = :at WHERE id = :id"), {"at": stamp, "id": entry_id}
        )
    session.commit()


@pytest.fixture()
def big(client, session):
    _build(session)
    return client


def _measure(client, path: str) -> tuple[int, float, int, int]:
    seen: list[str] = []

    def record(_conn, _cursor, statement, *_args, **_kwargs):
        seen.append(statement)

    engine = deps.get_db().engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        began = time.perf_counter()
        response = client.get(path)
        elapsed = time.perf_counter() - began
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(seen), elapsed, response.status_code, len(response.content)


def test_the_routes_stay_inside_their_budget_at_2000_notes(big):
    problems = []
    for path, (budget, limit, most) in BUDGET.items():
        _measure(big, path)  # warm: the first call builds caches and matrices
        runs = [_measure(big, path) for _ in range(3)]
        statements, _, status, size = runs[0]
        seconds = min(run[1] for run in runs)
        print(f"PERF2000 {path}: {statements} statements, {seconds * 1000:.0f} ms, {size} bytes, status {status}")
        if status != 200:
            problems.append(f"{path}: status {status}")
        if statements > budget:
            problems.append(f"{path}: {statements} statements, the budget is {budget}")
        if size > most:
            problems.append(f"{path}: {size} bytes, the budget is {most}")
        if seconds > limit:
            problems.append(f"{path}: {seconds:.2f} s, the budget is {limit} s")
    assert not problems, "; ".join(problems)


def test_pf7_a_slow_read_reaches_the_logs_report_and_a_slow_write_waits_for_its_model():
    """PF7: the 150 to 210 ms list routes never reached the report at 1 s."""
    from tessellate.core import diagring

    diagring._requests.clear()
    diagring.note_request("GET", "/entries", diagring.SLOW_GET_MS + 1, 200)
    diagring.note_request("GET", "/entries", diagring.SLOW_GET_MS - 1, 200)
    diagring.note_request("POST", "/chat", diagring.SLOW_GET_MS + 1, 200)
    diagring.note_request("POST", "/entries", diagring.SLOW_REQUEST_MS + 1, 200)
    kept = [(row["method"], row["route"]) for row in diagring._requests]
    diagring._requests.clear()
    assert len(kept) == 2 and kept[0][0] == "GET" and kept[1][0] == "POST"
