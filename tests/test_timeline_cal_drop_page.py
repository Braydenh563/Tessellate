"""A day page dropped on another day in the calendar (LEDGER L910).

Measured in Chromium with touch emulation at 1024 (synthetic dragstart, dragover
and drop on the month view): the page moves and the toast says "The page for
2026-11-12 is now the page for 2026-11-17."; onto a day that has a page it stays
and says "That day already has a page; open it to write there."; onto its own day
nothing happens. These pin the same three answers without a browser, and that
anything but a reminder or a day page is refused with its reason.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests import _js_scope
from tests._app_js import JS_DIR

CAL = _js_scope.unwrapped((JS_DIR / "timeline-calendar.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    match = re.search(rf"^( *)(?:async )?function {name}\(.*?^\1\}}", CAL, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def _run(row: dict, day: str, pages: dict) -> dict:
    script = f"""
const log = {{ toasts: [], puts: [], undo: [] }};
const timelineCal = {{ rows: [{json.dumps(row)}], url: "x", drag: null }};
const TIMELINE_CAL_DRAG = "x";
const dailyNoteTitle = (k) => k;
const timelineBucketKey = (when, scale) => when.slice(0, 10);
const timelineIsDailyNote = (r) => r.title === r.when.slice(0, 10);
const timelineCalDays = () => new Map(Object.entries({json.dumps(pages)}));
const toast = (text) => log.toasts.push(text);
const paintTimeline = () => {{}};
const pushUndo = (label) => log.undo.push(label);
const $ = () => ({{ querySelector: () => null, dataset: {{}} }});
const apiJson = async (url, opts) => {{
  if (!opts) return {{ content: "2026-11-12\\n\\nbody", content_hash: "h" }};
  log.puts.push(JSON.parse(opts.body).content);
  return {{}};
}};
{_fn("timelineCalDropTarget")}
{_fn("timelineCalDragEnd")}
{_fn("timelineCalMovePage")}
{_fn("timelineCalMoveReminder")}
{_fn("timelineCalDrop")}
const target = {{ dataset: {{ calDay: {json.dumps(day)} }} }};
const event = {{ target: {{ closest: () => target }}, preventDefault() {{}}, dataTransfer: {{ getData: () => {json.dumps(row["key"])} }} }};
timelineCalDrop(event).then(() => process.stdout.write(JSON.stringify(log)));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


PAGE = {"key": "note:5", "id": 5, "kind": "note", "title": "2026-11-12", "when": "2026-11-12T09:00:00"}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_day_page_dropped_on_an_empty_day_takes_that_day_as_its_title():
    log = _run(PAGE, "2026-11-17", {})
    assert log["puts"] == ["2026-11-17\n\nbody"]
    assert log["toasts"] == ["The page for 2026-11-12 is now the page for 2026-11-17."]
    assert log["undo"] == ["Moved the page for 2026-11-12 to 2026-11-17"]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_day_page_dropped_on_a_day_with_a_page_stays_and_says_why():
    log = _run(PAGE, "2026-11-17", {"2026-11-17": {"page": {"key": "note:6"}}})
    assert log["puts"] == [] and log["undo"] == []
    assert log["toasts"] == ["That day already has a page; open it to write there."]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_day_page_dropped_on_its_own_day_does_nothing():
    log = _run(PAGE, "2026-11-12", {})
    assert log == {"toasts": [], "puts": [], "undo": []}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_plain_note_is_refused_with_the_reason():
    note = {**PAGE, "key": "note:9", "title": "Lunch ideas"}
    log = _run(note, "2026-11-17", {})
    assert log["puts"] == []
    assert log["toasts"] == ["Only a reminder or a day page moves by dragging; a meeting's date is in its note."]
