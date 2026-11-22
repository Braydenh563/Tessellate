"""The calendar's double tap (LEDGER L911).

Measured in Chromium with `hasTouch` and `isMobile` at 1024 (two `touchscreen.tap`
calls 90 ms apart on the 20 Nov cell): the browser sends the clicks with `detail`
1 then 2, the first tap's pending open-the-day is cancelled, and the add sheet
opens on 2026-11-20 at 09:00. One tap alone opens the Day view after the
double-click window. This runs the click handler itself with those two clicks.
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


def _handler() -> str:
    match = re.search(r'box\.addEventListener\("click", (\(event\) => \{.*?^    \})\);', CAL, re.S | re.M)
    assert match, "the calendar's click handler is gone"
    return match.group(1)


def _run(clicks: list[tuple[int, int]], cls: str = "timeline-cal-stop", hour: str | None = None) -> dict:
    """`clicks` are (detail, wait in ms before it); returns what the handler asked for."""
    script = f"""
const log = {{ added: [], picked: [] }};
const TIMELINE_CAL_DOUBLE_MS = 40;
const timelineCal = {{ pickTimer: 0 }};
const timelineCalAdd = (day, hour) => log.added.push([day, hour]);
const timelineCalPick = (day) => log.picked.push(day);
const timelineCalSetSpan = () => {{}};
const cell = {{ dataset: {{ calDay: "2026-11-20"{', calHour: "%s"' % hour if hour is not None else ""} }}, classList: {{ contains: (c) => c === {json.dumps(cls)} }} }};
const handler = {_handler()};
const event = (detail) => ({{ detail, target: {{ closest: (sel) => (sel.includes("data-cal-span") ? null : sel.startsWith("button") ? null : cell) }} }});
(async () => {{
  for (const [detail, wait] of {json.dumps(clicks)}) {{
    await new Promise((r) => setTimeout(r, wait));
    handler(event(detail));
  }}
  await new Promise((r) => setTimeout(r, 120));
  process.stdout.write(JSON.stringify(log));
}})();
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_two_taps_add_on_the_day_and_never_open_it():
    assert _run([(1, 0), (2, 10)]) == {"added": [["2026-11-20", None]], "picked": []}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_one_tap_opens_the_day_after_the_double_window():
    assert _run([(1, 0)]) == {"added": [], "picked": ["2026-11-20"]}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_two_taps_on_an_hour_cell_add_at_that_hour():
    assert _run([(1, 0), (2, 10)], cls="timeline-cal-hourcell", hour="15") == {"added": [["2026-11-20", 15]], "picked": []}
