"""The perf budget, in CI (WORLD_CLASS_PLAN H9, row 27): the routes a boot and
the first clicks call, each with a budget, so a regression fails the build
like a lint rather than being found by a person a month later.

**Two numbers per route.** Statements against the database, which do not
depend on the machine: a route that starts loading every note one at a time
(the N+1 the 2026-10-03 performance pass took `/entries/reference-counts`
from 242 statements down to 6 for) fails here on any runner. And wall time,
generous enough for a busy CI runner and a sandbox at load 20, so it fails
only on a slowdown nobody could miss. The statement budgets were measured on
this notebook (300 notes, 5 documents, 20 reminders) and given room for a
statement or two of honest growth; raising one needs a reason in its
comment, the way the gzip caps do.

`boottime.js` and the per-action sweeps stay the browser's half; this is the
half every push runs.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import event

from tessellate.core import deps
from tessellate.entry import manager

#: route: (statement budget, seconds). Measured 2026-10-05 on the fixture
#: below; the statement figure in each comment is what was measured.
BUDGET = {
    "/entries?limit=60": (12, 2.0),  # measured 9 statements, 12 ms
    "/entries/reference-counts?ids=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20": (8, 1.0),  # 6, 16 ms
    "/insights/stats": (6, 1.0),  # 4, 7 ms
    "/insights/heatmap": (4, 1.0),  # 2, 6 ms
    "/categories": (5, 1.0),  # 3, 5 ms
    "/tags": (5, 1.0),  # 3, 6 ms
    "/reminders?limit=50": (5, 1.0),  # 3, 7 ms
    "/documents": (5, 1.0),  # 3, 6 ms
    "/conversations?limit=50": (5, 1.0),  # 3, 7 ms
    "/spaces": (4, 1.0),  # 2, 5 ms
}


@pytest.fixture()
def notebook(client, session):
    for n in range(300):
        manager.create_entry(
            session,
            f"Note {n} about the {['garden', 'boiler', 'rent', 'project', 'trip'][n % 5]}, tagged #t{n % 7}.",
            category_name=["Home", "Work", "Garden"][n % 3],
            tags=[f"t{n % 7}"],
        )
    for n in range(5):
        client.post("/documents", json={"title": f"Doc {n}", "content": "# Doc\n\nText."})
    for n in range(20):
        client.post("/reminders", json={"text": f"Reminder {n}", "due_at": "2099-01-01T09:00:00"})
    return client


def _measure(client, path: str) -> tuple[int, float, int]:
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
    return len(seen), elapsed, response.status_code


@pytest.mark.parametrize("path", list(BUDGET))
def test_each_route_stays_inside_its_budget(notebook, path):
    _measure(notebook, path)  # warm: the first call builds caches and matrices
    #: Wall time is the best of three: one CI run read /insights/heatmap at
    #: 1.20 s against a measured 6 ms (2026-10-05, Python 3.11 runner, the
    #: same route passing on 3.12 and 3.13 of that push), a stall of the
    #: runner rather than of the route. The minimum is what a timing gate
    #: compares, and a real slowdown is slow on all three. Statements are
    #: exact and read from the first of them.
    runs = [_measure(notebook, path) for _ in range(3)]
    statements, _, status = runs[0]
    seconds = min(run[1] for run in runs)
    budget, limit = BUDGET[path]
    assert status == 200, path
    assert statements <= budget, f"{path}: {statements} statements, the budget is {budget}"
    assert seconds <= limit, f"{path}: {seconds:.2f} s, the budget is {limit} s"


def test_a_deliberate_regression_is_caught(notebook, monkeypatch):
    """The gate's own proof: the same route made N+1 fails its budget."""
    from tessellate.api import entry_out

    real = entry_out.to_out_bulk

    def one_at_a_time(session, entries):
        for entry in entries:
            session.get(type(entry), entry.id, populate_existing=True)
        return real(session, entries)

    monkeypatch.setattr(entry_out, "to_out_bulk", one_at_a_time)
    statements, _seconds, _status = _measure(notebook, "/entries?limit=60")
    assert statements > BUDGET["/entries?limit=60"][0]
