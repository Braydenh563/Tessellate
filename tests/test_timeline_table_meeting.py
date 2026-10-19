"""INBOX 341: the Timeline table names a meeting as a Meeting, not a Note.

The Kind column read `TIMELINE_KIND_NAMES[row.kind]`, and a meeting is a note
placed by its own `date:`, so it said "Note". The column is hidden below 600px
(a phone's default view), so the title cell also wears the meeting mark.
"""
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "js"
JS = (JS_DIR / "timeline.js").read_text(encoding="utf-8")


def test_the_kind_cell_and_its_sort_share_one_name_that_knows_meetings():
    assert "function timelineKindName(row)" in JS
    body = JS[JS.index("function timelineKindName(row)") :][:400]
    assert '"Meeting"' in body and 'placedBy === "meeting"' in body
    assert "TIMELINE_KIND_NAMES[row.kind] ||" not in JS.replace(body, "")


def test_the_table_title_cell_carries_the_meeting_mark_on_a_phone():
    css = (JS_DIR.parent / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    phone = css[css.index("@media (max-width: 599.98px) {\n  .timeline-table .timeline-col-wide") :][:600]
    assert '.timeline-trow[data-placed="meeting"] .timeline-col-title::before' in phone
    assert 'content: "Meeting: "' in phone
