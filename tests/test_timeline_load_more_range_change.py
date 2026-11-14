"""Brief 101b: a load-more in flight when the range changes must not leave
the new range at its first 100 rows.

`renderTimeline` asks for the rest of the first 300 a frame after the rows
paint. One flag (`timelinePaging`) said "a request is out", for any range, so
a page still on its way for the old range made the new range's next page
return at once; the old page was then dropped (it belongs to a superseded
render) and nothing asked again until a scroll.
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
let timelineNextCursor = "old";
let timelineRows = [];
let timelineById = new Map();
const asked = [];
const pending = [];
const apiJson = (url) => { asked.push(url); return new Promise((resolve) => pending.push(resolve)); };
const timelineQuery = () => "/timeline?days=30";
const timelineRow = (row) => ({ ...row, when: new Date(row.at) });
const timelineViewMode = () => "feed";
const appended = [];
const appendTimelineRows = (rows) => appended.push(...rows.map((r) => r.key));
const drawTimelineScrubber = () => {};
const paintTimeline = () => {};
%s
(async () => {
  const first = timelineLoadMore(200);            // the old range's page, in flight
  timelineRenders.n = 2;                          // the range changes
  timelineNextCursor = "new";
  const second = timelineLoadMore(200);           // the new range's next page
  const askedBeforeAnswers = asked.length;
  pending.forEach((resolve, i) => resolve({ next_cursor: null, rows: [{ key: "r" + i, at: "2026-01-0" + (i + 1) }] }));
  await Promise.all([first, second]);
  process.stdout.write(JSON.stringify({ askedBeforeAnswers, appended, cursor: timelineNextCursor }));
})();
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_new_range_asks_for_its_rest_while_the_old_page_is_in_flight():
    source = (JS_DIR / "timeline.js").read_text(encoding="utf-8")
    state = re.search(r"^let timelinePaging\w* = [^;]*;", source, re.M)
    func = re.search(r"^async function timelineLoadMore\(limit = TIMELINE_PAGE\) \{.*?^\}", source, re.S | re.M)
    assert func, "timelineLoadMore is gone from the timeline script"
    script = HARNESS % ((state.group(0) if state else "") + "\nconst TIMELINE_PAGE = 300;\n" + func.group(0))
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["askedBeforeAnswers"] == 2, "the new range never asked for the rest of its first page"
    assert out["appended"] == ["r1"], "only the new range's page is appended; the old range's is dropped"
