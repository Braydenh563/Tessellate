"""L-world-class-354: two dashboard reads sorted every note, parsing dates inside the comparator
(dashContinueNote 86ms, the recent-notes widget 33ms, at 4x CPU on 5,000 notes)."""

from tests._app_js import frontend_text


def _fn(name, end):
    js = frontend_text("dashboard.js")
    start = js.index(f"function {name}(")
    return js[start : js.index(end, start)]


def test_continue_takes_the_latest_in_one_pass():
    body = _fn("dashContinueNote", "const DASH_VIEW_LABELS")
    assert ".sort(" not in body
    assert "for (const entry of entries)" in body and "time > bestTime" in body


def test_recent_notes_parse_each_date_once():
    body = _fn("renderRecentNotesWidget", "async function renderTopTagsWidget")
    assert "new Date(entry.created_at).getTime()" in body
    assert "new Date(b.created_at) - new Date(a.created_at)" not in body
