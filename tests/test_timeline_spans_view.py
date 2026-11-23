"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

A written range draws as a span (TIMELINE_PLAN decision 13, L-timeline-4).

The server serves `until` on a ranged note's row (test_timeline_spans.py);
the feed and the table label it "3 Mar to 7 Mar", and the calendar draws a
"continues" ghost on each day after the first through the last. The helpers
run under node with a fixed clock.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
TIMELINE = (JS / "timeline.js").read_text()
CALENDAR = (JS / "timeline-calendar.js").read_text()


def _function(text: str, name: str) -> str:
    start = re.search(rf"^\s*(?:\S+ = )?function {name}\(", text, re.M).start()
    end = re.compile(r"\n  }\n" if text[start:].startswith("  ") else r"\n};?\n").search(text, start).end()
    return text[start:end]


def _node(body: str) -> object:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = (
        "const RealDate = Date;\n"
        "globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [2026, 10, 12, 9])); } };\n"
        'const TIMELINE_ROW_FULL_DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });\n'
        'TIMELINE_ROW_FULL_DATE.thisYear = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });\n'
        + _function(TIMELINE, "timelineSpanLabel")
        + "\n"
        + _function(CALENDAR, "timelineCalSpanKeys")
        + "\n"
        + body
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_calendar_continues_a_span_on_each_later_day_through_the_last():
    keys = _node('console.log(JSON.stringify(timelineCalSpanKeys("2026-03-03", "2026-03-07")))')
    assert keys == ["2026-03-04", "2026-03-05", "2026-03-06", "2026-03-07"]


def test_a_span_crosses_a_month_and_a_year_end():
    keys = _node('console.log(JSON.stringify(timelineCalSpanKeys("2026-12-30", "2027-01-02")))')
    assert keys == ["2026-12-31", "2027-01-01", "2027-01-02"]


def test_a_single_day_has_no_ghosts_and_a_span_is_capped_at_a_year():
    out = _node(
        'console.log(JSON.stringify([timelineCalSpanKeys("2026-03-03", "2026-03-03").length,'
        ' timelineCalSpanKeys("2026-01-01", "2030-01-01").length]))'
    )
    assert out == [0, 366]


def test_the_label_says_the_range_with_the_year_only_when_it_is_not_this_one():
    out = _node(
        "console.log(JSON.stringify([TIMELINE_ROW_FULL_DATE.span(new Date(2026, 2, 3), \"2026-03-07\"),"
        " TIMELINE_ROW_FULL_DATE.span(new Date(2027, 2, 3), \"2027-03-07\")]))"
    )
    assert out == ["3 Mar to 7 Mar", "3 Mar 2027 to 7 Mar 2027"]


def test_rows_carry_until_and_the_calendar_draws_span_ghosts_not_draggable():
    assert "until: entry.until || null" in TIMELINE
    assert "timelineCalSpanKeys(timelineBucketKey(row.when, \"day\"), row.until)" in CALENDAR
    assert "span: true" in CALENDAR and 'if (row.span) return "ph:arrows-horizontal";' in CALENDAR
    assert "item.draggable = !row.also;" in CALENDAR  # a span ghost is `also`, so it does not drag
    # Both the feed row and the table label a span by its range.
    assert TIMELINE.count("row.until ? TIMELINE_ROW_FULL_DATE.span(row.when, row.until)") == 2
