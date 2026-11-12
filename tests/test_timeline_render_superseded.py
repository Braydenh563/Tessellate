"""L483: a second render started while the first is in flight paints once.

A `timeline-days` change arriving after the tab's own render (the on-this-day
row, a typed range, the calendar's custom range) started a second
`renderTimeline` while the first was still waiting on `/timeline`. Both
painted, and when the older answer landed last it painted the old range over
the new one (once in nine runs at 5,000 notes). The older answer is dropped.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

HARNESS = r"""
const timelineRenders = { n: 0, pagingFor: 0, total: null };
let timelineDensity = {}, timelineNextCursor = null, timelineRows = [], timelineById = new Map(), timelineOpenKey = null, timelineFilter = null;
const pending = [];
const apiJson = (url) => new Promise((resolve) => pending.push({ url, resolve }));
const loadMapBoardIndex = async () => {};
let range = "30";
const timelineQuery = () => "/timeline?days=" + range;
const TIMELINE_FIRST = 100;
const $ = () => ({ closest: () => true });
const showSkeletons = () => {}, clearSkeletons = () => {}, surfaceFailed = () => {}, surfaceRecovered = () => {};
const timelineRow = (row) => ({ ...row, when: new Date(row.at) });
const fillTimelineBandOptions = () => {}, renderTimelineKinds = () => {};
const painted = [];
const paintTimeline = () => painted.push(timelineRows.map((r) => r.key).join(","));
const timelineViewMode = () => "table";
const requestAnimationFrame = () => {};
const timelineRecall = { hold: () => {} };  // the on-this-day row's hold, outside this test
%s
(async () => {
  const first = renderTimeline();
  range = "365";
  const second = renderTimeline();
  await new Promise((r) => setTimeout(r));
  pending[1].resolve({ rows: [{ key: "new", at: "2026-01-02" }] });
  await second;
  pending[0].resolve({ rows: [{ key: "old", at: "2026-01-01" }] });
  await first;
  process.stdout.write(JSON.stringify({ painted, rows: timelineRows.map((r) => r.key) }));
})();
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_older_render_landing_last_is_dropped():
    source = (JS_DIR / "timeline.js").read_text(encoding="utf-8")
    func = re.search(r"^async function renderTimeline\(\) \{.*?^\}", source, re.S | re.M)
    assert func, "renderTimeline is gone from the timeline script"
    done = subprocess.run(["node", "-e", HARNESS % func.group(0)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    out = json.loads(done.stdout)
    assert out["painted"] == ["new"], "the superseded render painted too"
    assert out["rows"] == ["new"]
