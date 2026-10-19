"""INBOX 1316: "the timeline side graph should scroll higher if I scroll to
future dates". The strip's span reaches the newest row and the week ahead,
and the empty days ahead are watched like rows, so the window rises with
the feed. The strip itself is drawn by the lazy labels file now."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _body(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start)]


def test_span_reaches_the_newest_row_and_the_week_ahead():
    span = _body((JS / "timeline.js").read_text(encoding="utf-8"), "timelineDensitySpan")
    assert "timelineRows[0]" in span and "7 * 864e5" in span and "timelineSpanCache.head === head" in span


def test_empty_days_ahead_move_the_window():
    text = (JS / "timeline.js").read_text(encoding="utf-8")
    assert 'if (scale === "day") timelineWatchRow(section);' in _body(text, "timelineBucketSection")
    assert "el.dataset.empty ?" in _body(text, "drawTimelineWindow")


def test_the_strip_is_drawn_by_the_lazy_file():
    boot = (JS / "timeline.js").read_text(encoding="utf-8")
    assert "ok && drawTimelineStrip()" in _body(boot, "drawTimelineScrubber")
    assert "function drawTimelineStrip()" in (JS / "timeline-ticks.js").read_text(encoding="utf-8")
