"""L-world-class-68: `GET /reminders?only_done=true` is the Done section's pager.

The open set stays loaded whole (badge, status bar, due timer read it); the
done rows page by cursor on scroll, and the total counts the same filter."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    freeze_reminder_clock(monkeypatch)


def _make(client, n_open, n_done):
    for i in range(n_open + n_done):
        due = (FIXED_NOW + timedelta(hours=i + 1)).isoformat()
        made = client.post("/reminders", json={"text": f"r{i}", "due_at": due}).json()
        if i >= n_open:
            ticked = client.put(f"/reminders/{made['id']}", json={"done": True})
            assert ticked.status_code == 200


def test_only_done_filters_and_counts_the_same_set(client):
    _make(client, 3, 5)
    response = client.get("/reminders", params={"only_done": True})
    rows = response.json()
    assert len(rows) == 5 and all(r["done"] for r in rows)
    assert response.headers["X-Total-Count"] == "5"
    open_rows = client.get("/reminders", params={"include_done": False})
    assert len(open_rows.json()) == 3 and open_rows.headers["X-Total-Count"] == "3"


def test_only_done_pages_by_cursor_without_gaps(client):
    _make(client, 2, 7)
    seen, cursor = [], None
    for _ in range(10):
        params = {"only_done": True, "limit": 3}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/reminders", params=params)
        seen += [r["id"] for r in response.json()]
        cursor = response.headers.get("X-Next-Cursor")
        if not cursor:
            break
    assert len(seen) == 7 and len(set(seen)) == 7


def test_the_tabs_page_on_scroll_and_filters_keep_the_whole_list():
    """The Reminders tab reads the open set whole and the done rows by cursor;
    the Library pages only an unfiltered, newest-first list (a search, a
    property, another sort or a page size reads it all, as before)."""
    from tests._app_js import app_js_text

    text = app_js_text()
    assert "only_done=true&limit=" in text and "/reminders?include_done=false" in text
    assert '"/reminders?only_done=true", 200' in text
    library = (Path(__file__).parents[1] / "frontend/js/library.js").read_text(encoding="utf-8")
    assert '!needle && !libraryDocsProperty && libraryDocSort() === "newest"' in library
    assert "libraryDocsScroll.cursor" in library
