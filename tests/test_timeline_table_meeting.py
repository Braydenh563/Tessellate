"""INBOX 341: the Timeline table names a meeting as a Meeting, not a Note.

The Kind column read `TIMELINE_KIND_NAMES[row.kind]`, and a meeting is a note
placed by its own `date:`, so it said "Note". The column is hidden below 600px
(a phone's default view), so the title cell wears the feed's kind mark (LEDGER L485; it replaced a "Meeting: " text prefix).
"""
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "js"
JS = (JS_DIR / "timeline.js").read_text(encoding="utf-8")


def test_the_kind_cell_and_its_sort_share_one_name_that_knows_meetings():
    assert "function timelineKindName(row)" in JS
    body = JS[JS.index("function timelineKindName(row)") :][:400]
    assert '"Meeting"' in body and 'placedBy === "meeting"' in body
    assert "TIMELINE_KIND_NAMES[row.kind] ||" not in JS.replace(body, "")


def test_the_table_title_cell_wears_the_feeds_kind_mark_at_every_width():
    """L485: one mark builder for the rail and the table, named for a screen reader."""
    assert "function timelineKindMark(row)" in JS
    assert JS.count("timelineRowElement.kindMark(row)") >= 2  # the feed row and the table row (a property: the scope ratchet)
    table = JS[JS.index("function timelineTableRow(row)") :][:4000]
    assert "const mark = timelineRowElement.kindMark(row);" in table
    assert 'mark.setAttribute("aria-label", timelineKindName(row));' in table
    assert "title.append(mark, row.title);" in table
    css = (JS_DIR.parent / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert ".timeline-col-title > .timeline-row-mark {" in css
    # The old text prefix is gone: the mark carries a meeting now.
    assert 'content: "Meeting: "' not in css
