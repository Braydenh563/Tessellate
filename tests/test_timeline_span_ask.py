"""The span review has a keyboard and phone way in (L-timeline-2, second part).

The brush is Shift and a mouse drag on the strip, and the strip is hidden on a
phone; Options, Review some days asks for the two days on the sheet recipe and
opens the same `/timeline/digest` review.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend/js/timeline.js").read_text()
HTML = (ROOT / "frontend/index.html").read_text()


def test_options_has_review_some_days():
    menu = HTML[HTML.index('id="timeline-options"') :][:9000]
    assert 'id="timeline-span-btn"' in menu and "Review some days" in menu


def test_the_ask_sheet_reads_two_dates_and_opens_the_review():
    ask = JS[JS.index("  ask() {") :][:2600]
    assert 'type: "date"' in ask and '"timeline-span-from"' in ask and '"timeline-span-to"' in ask
    assert "[from.value, to.value].sort()" in ask  # From after To is turned round
    assert "await timelineSpans.open(start, end)" in ask
    assert 'setBusy(review, true, "Reading…")' in ask  # a model takes seconds: the spinner recipe
    assert '$("timeline-span-btn").addEventListener("click"' in JS


def test_help_and_guide_name_it():
    guide = (ROOT / "src/tessellate/ai/help_topics_core.py").read_text()
    assert "Review some days" in guide
    assert HTML.count("Review some days") >= 2  # the menu item and the popover
