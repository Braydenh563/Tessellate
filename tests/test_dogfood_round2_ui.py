"""Blind-test round 2 (dog2-1025): UI fixes the suite can only pin by source.

Each check names the finding it guards; the measured behaviour was driven in
Chromium (numbers in the commit).
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_month_calendar_scrolls_today_into_view():
    # 5: a 6-row month is 729px in a 579px pane at 1280x800; today's row was clipped.
    src = (JS / "timeline-calendar.js").read_text()
    assert "timelineCalShowToday" in src
    assert 'span === "month" && timelineCal.painted !== drawn' in src
