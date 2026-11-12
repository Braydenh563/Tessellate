"""The characters' arrival timer is named and holds no job (INBOX 1741).

The owner's log: `inline TimerHandler:setTimeout 290ms` after the dashboard opened. A long-animation-frame
entry names a script by its function, and an anonymous arrow in `setTimeout` reads as "inline". The first of
the queued jobs also ran inside that timer: at 6x CPU it was 65ms, 60 of them the chat heads' dressing.
"""

from __future__ import annotations

from pathlib import Path

ATLAS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _body() -> str:
    start = ATLAS.index("function charactersArrived()")
    return ATLAS[start : ATLAS.index("\n}\n", start) + 3]


def test_the_arrival_timer_has_a_name() -> None:
    assert "setTimeout(function charactersArrivedTask() {" in _body()


def test_no_job_runs_inside_the_arrival_timer() -> None:
    body = _body()
    task = body[: body.index("const step = () => {")]
    assert "runCharacterJob(" not in task
    assert "    setTimeout(step, 0);\n  }, 0);" in body, "the queue opens on a task of its own"


NOTES = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")


def test_the_category_list_is_not_drawn_behind_another_tab() -> None:
    """The first page of notes drew the Notes tab's sidebar on the dashboard (11 and 29ms at 6x CPU)."""
    start = NOTES.index("function renderSidebar() {")
    head = NOTES[start : NOTES.index("const counts = new Map();", start)]
    assert '$("tab-notes").classList.contains("hidden")' in head
    assert 'dataset.stale = "1"' in head and "return;" in head, "owed with the list's own debt"


def test_the_debt_is_paid_when_the_list_is_drawn_for_a_visible_tab() -> None:
    start = NOTES.index("function renderEntries(appendOnly = false) {")
    first = NOTES[start : NOTES.index("\n", NOTES.index("renderSidebar()", start))]
    assert 'dataset.stale) renderSidebar()' in first
