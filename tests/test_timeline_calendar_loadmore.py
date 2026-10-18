"""The calendar's count is the calendar's (TIMELINE_PLAN section 9, Not verified).

A 1,000-note month measured with `scratchpad/ui-sweeps/calcount1018.js`: the
dock's count read "1000 items · October 2026" for a moment, then "192 notes · 7
days", the hidden feed's. `timelineLoadMore` (the scroll handler's, and the
follow-up page a render asks for) appended its rows to the feed whichever view
was showing, and the feed's painter writes the count. In the calendar the feed
is emptied and hidden, and the calendar reads its own period; a page for the
feed has nothing to draw into and no right to the chip.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

HARNESS = r"""
const timelineRenders = { n: 1 };
let timelineNextCursor = "next";
let timelineRows = [];
let timelineById = new Map();
const apiJson = () => Promise.resolve({ next_cursor: null, rows: [{ key: "r1", at: "2026-01-01" }] });
const timelineQuery = () => "/timeline?days=30";
const timelineRow = (row) => ({ ...row, when: new Date(row.at) });
const timelineViewMode = () => %s;
const calls = [];
const appendTimelineRows = () => calls.push("append");
const drawTimelineScrubber = () => {};
const paintTimeline = () => calls.push("paint");
%s
(async () => {
  await timelineLoadMore(200);
  process.stdout.write(JSON.stringify({ calls, rows: timelineRows.length }));
})();
"""


def _run(mode: str) -> dict:
    source = (JS_DIR / "timeline.js").read_text(encoding="utf-8")
    state = re.search(r"^let timelinePaging\w* = [^;]*;", source, re.M)
    func = re.search(r"^async function timelineLoadMore\(limit = TIMELINE_PAGE\) \{.*?^\}", source, re.S | re.M)
    assert func, "timelineLoadMore is gone from the timeline script"
    script = HARNESS % (json.dumps(mode), (state.group(0) if state else "") + "\nconst TIMELINE_PAGE = 300;\n" + func.group(0))
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("mode,calls", [("feed", ["append"]), ("table", ["paint"]), ("calendar", [])])
def test_a_page_of_rows_is_drawn_only_by_the_view_that_shows_rows(mode, calls):
    out = _run(mode)
    assert out["rows"] == 1, "the rows are kept for every view"
    assert out["calls"] == calls
