"""L-timeline-1: a run of empty weeks in the feed says so, with a way in.

A notebook that skipped three weeks reads, on the day and week scales, as two
adjacent dates three weeks apart: the gap is there but nothing points at it.
A quiet line between the two sections names it ("Nothing written for 3
weeks") and its button opens the page for the first empty day, which is
`openDayPage`: the composer, nothing saved until Save.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

TIMELINE = (JS_DIR / "timeline.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = TIMELINE.index(f"function {name}(")
    match = re.search(r"\n}\n", TIMELINE[start:])
    assert match
    return TIMELINE[start : start + match.end()]


def _spans() -> str:
    """`timelineSpans`, the one name the gap lines and the brush share."""
    start = TIMELINE.index("const timelineSpans = {")
    return TIMELINE[start : TIMELINE.index("\n};\n", start) + 4]


def _method(name: str) -> str:
    spans = _spans()
    start = re.search(rf"\n  (?:async )?{name}\(", spans).start()
    return spans[start : spans.index("\n  },", start) + 5]


HARNESS = r"""
const timelineBucketKey = (d) => d.toISOString().slice(0, 10);
%s
%s
const cases = [
  ["2026-03-01", "2026-02-27", "day"],
  ["2026-03-10", "2026-03-02", "day"],
  ["2026-03-23", "2026-03-02", "week"],
  ["2026-03-09", "2026-03-02", "week"],
  ["2026-03", "2026-01", "month"],
];
process.stdout.write(JSON.stringify(cases.map((c) => timelineSpans.gap(...c))));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_a_week_or_more_with_nothing_is_a_gap_and_less_is_not():
    harness = HARNESS % (_function("timelineDayShift"), _spans())
    out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30, env={**os.environ, "TZ": "UTC"})
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    # Day scale: two empty days is no gap; seven (03-03 to 03-09) is.
    assert got[0] is None
    assert got[1] == {"days": 7, "first": "2026-03-03"}
    # Week scale: the weeks of 03-09 and 03-16 are empty, the first is 03-09.
    assert got[2] == {"days": 14, "first": "2026-03-09"}
    # Adjacent weeks, and any month scale, have no marker.
    assert got[3] is None
    assert got[4] is None


def test_the_feed_and_the_next_page_both_draw_the_marker():
    for name in ("paintTimelineFeed", "appendTimelineRows"):
        assert "timelineSpans.gapMarker(" in _function(name), name


def test_the_marker_opens_the_day_and_does_not_write():
    body = _method("gapMarker")
    assert "openDayPage(gap.first)" in body
    assert "What happened here?" in body
    assert "apiJson" not in body
