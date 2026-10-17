"""The feed's days ahead (INBOX 904 B72, the owner: "on the timeline I wanna be
able to scroll above today's date to see future dates").

On the day scale the feed holds the week ahead above today, each day a head
with an Add on the ones with nothing in them (the calendar's add sheet), and a
fresh read lands on today with the future above it. Measured before: a
notebook with nothing ahead had today as its first bucket, so there was
nothing above today to scroll to; and an empty today was drawn first even
when later days had rows, above them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

TL = (JS_DIR / "timeline.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    match = re.search(rf"^(?:async )?function {name}\(.*?^\}}", TL, re.S | re.M)
    assert match, f"{name} is gone from timeline.js"
    return match.group(0)


def _ahead(buckets: list[dict], today: str) -> list[str]:
    script = "\n".join(_fn(n) for n in ("timelineBucketKey", "timelineDayShift", "timelineAheadBuckets"))
    script += f"\nprocess.stdout.write(JSON.stringify(timelineAheadBuckets({json.dumps(buckets)}, {json.dumps(today)}).map((b) => [b.key, b.rows.length])));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_week_ahead_and_today_are_there_with_nothing_in_them():
    got = _ahead([{"key": "2026-10-15", "rows": [1, 2]}], "2026-10-17")
    assert [k for k, _ in got] == [
        "2026-10-24", "2026-10-23", "2026-10-22", "2026-10-21", "2026-10-20",
        "2026-10-19", "2026-10-18", "2026-10-17", "2026-10-15",
    ]
    assert got[-1] == ["2026-10-15", 2] and all(n == 0 for _, n in got[:-1])


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_days_with_rows_keep_them_and_the_order_stays_newest_first():
    got = _ahead([{"key": "2026-11-02", "rows": [1]}, {"key": "2026-10-20", "rows": [1, 2, 3]}, {"key": "2026-10-10", "rows": [1]}], "2026-10-17")
    keys = [k for k, _ in got]
    assert keys == sorted(keys, reverse=True), "newest first, an empty today below the days ahead"
    assert dict(got)["2026-10-20"] == 3 and dict(got)["2026-11-02"] == 1 and dict(got)["2026-10-17"] == 0
    assert len(keys) == len(set(keys)), "a day with rows is not drawn twice"


def test_a_fresh_read_lands_on_today_and_an_empty_day_ahead_offers_add():
    render = _fn("renderTimeline")
    assert "timelineScrollToToday(" in render, "a fresh read lands on today, the days ahead above it"
    assert "timelineScrollToToday(" in TL[TL.index('$("timeline-jump-today")'):], "the dock's Today uses the same scroll"
    section = _fn("timelineBucketSection")
    assert 'timelineCalendarCall("timelineCalAdd", bucket.key)' in section, "an empty day ahead opens the calendar's add sheet"
    assert "timelineAheadBuckets(" in _fn("paintTimelineFeed")
