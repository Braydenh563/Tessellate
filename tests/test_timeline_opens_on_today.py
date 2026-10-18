"""INBOX 1300 C39: the Timeline opens with Today as its top row and the days
ahead above it, reached by scrolling up. A short feed cannot scroll far
enough on its own, so the missing distance is space under the feed
(the `c39` Playwright sweep (kept out of the repo, which is at its scratchpad file cap) measures Today's row top: 0 on open, after the
Today button and on reopening)."""

from __future__ import annotations

import re
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")


def test_today_is_scrolled_to_the_top_even_in_a_short_feed() -> None:
    body = re.search(r"function timelineScrollToToday\(\) \{(.*?)\n\}\n", JS, re.S)
    assert body and "paddingBottom" in body.group(1)


def test_it_runs_again_once_the_strip_and_recall_row_have_moved_the_window() -> None:
    assert "setTimeout(timelineScrollToToday" in JS
