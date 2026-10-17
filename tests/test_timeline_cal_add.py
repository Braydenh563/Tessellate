"""Adding on a day from the calendar (TIMELINE_PLAN section 12 row 6; INBOX 904
B72, the owner: "I wanna be able to double click on a date and be able to add an
event and set a reminder").

A double click on a day (or an hour), the head's Add and N open one sheet with
the day filled: a reminder, or an event saved as a meeting note with a reminder
at its start. The day and time it opens with are `timelineCalAddStart`'s, and
what the words' chips read moves them (`timelineCalAddFields`), so the saved due
day is the cell's unless the words name another.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

CAL = (JS_DIR / "timeline-calendar.js").read_text(encoding="utf-8")
#: Its own lazy file: most visits to the calendar add nothing.
ADD = (JS_DIR / "timeline-cal-add.js").read_text(encoding="utf-8")


def _fn(name: str, text: str = ADD) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", text, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def _run(expr: str):
    script = _fn("timelineCalAddStart") + "\n" + _fn("timelineCalAddFields") + f"\nprocess.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


NOW = 'new Date(2026, 9, 17, 14, 20)'


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_later_day_opens_at_nine_and_an_hour_cell_at_its_hour():
    assert _run(f'timelineCalAddStart("2026-10-24", null, {NOW})') == {"date": "2026-10-24", "time": "09:00"}
    assert _run(f'timelineCalAddStart("2026-10-24", 15, {NOW})') == {"date": "2026-10-24", "time": "15:00"}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_today_opens_at_the_next_hour_once_nine_has_gone():
    assert _run(f'timelineCalAddStart("2026-10-17", null, {NOW})') == {"date": "2026-10-17", "time": "15:00"}
    assert _run('timelineCalAddStart("2026-10-17", null, new Date(2026, 9, 17, 7, 5))') == {"date": "2026-10-17", "time": "09:00"}
    #: Late in the evening the next hour is tomorrow, so the day keeps its last quarter.
    assert _run('timelineCalAddStart("2026-10-17", null, new Date(2026, 9, 17, 23, 30))') == {"date": "2026-10-17", "time": "23:45"}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_chips_move_the_fields_and_the_cell_holds_otherwise():
    typed = '{"date": "2026-10-24", "time": "09:00"}'
    assert _run(f"timelineCalAddFields(null, {typed})") == {"date": "2026-10-24", "time": "09:00"}
    assert _run(f'timelineCalAddFields({{"date": null, "time": "15:30"}}, {typed})') == {"date": "2026-10-24", "time": "15:30"}
    said_day = '{"spans": [{"kind": "date", "rank": 0}]}'
    said_time = '{"spans": [{"kind": "time", "rank": 0}]}'
    assert _run(f'timelineCalAddFields({{"date": "2026-10-30", "time": null, "reading": {said_day}}}, {typed})') == {"date": "2026-10-30", "time": "09:00"}
    #: "at 3pm" alone: the reading puts it on its next 3pm (measured: the day
    #: after today), and the sheet keeps the day that was pressed.
    assert _run(f'timelineCalAddFields({{"date": "2026-10-18", "time": "15:00", "reading": {said_time}}}, {typed})') == {"date": "2026-10-24", "time": "15:00"}


def test_every_door_opens_the_one_sheet():
    keys = _fn("timelineCalKeys", CAL)
    assert re.search(r'"n" \|\| event\.key === "N"\) timelineCalAdd\(key', keys), "N opens the sheet on the day"
    assert "timelineCalNewReminder" not in CAL, "the old N door (the reminders tab) is replaced, not kept beside"
    assert 'calAct = "add"' in _fn("timelineCalHead", CAL), "the head's Add, for a pointer with no double click"
    assert "event.detail" in CAL and "timelineCalAdd(" in CAL, "a double click on a day opens the sheet"
    assert 'lazyScript("/js/timeline-cal-add.js")' in _fn("timelineCalAdd", CAL)
    assert "openSheet(" in _fn("timelineCalAddOpen"), "the sheet recipe (DESIGN.md), not a hand-built dialog"
    sheet = ADD
    assert '"/reminders"' in sheet and '"/meetings"' in sheet, "a reminder, or an event as a meeting note"
    assert "quickAddAttach(" in sheet, "the words read as quick add's chips"
    assert "reminderMadeUndo(" in sheet and "pushRoutePairUndo(" in sheet, "every add is on the undo bar"
