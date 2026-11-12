"""The web-search store (CHAT_PLAN 2026-11-11 decision): pages fetched in a chat
are kept on this computer for 7 days, with a switch, Clear, and a re-fetch."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tessellate.core import deps
from tessellate.core.database import WebPage, utcnow
from tessellate.search import websearch

ROOT = Path(__file__).resolve().parents[1]
PAGE = {"url": "https://example.org/a", "domain": "example.org", "title": "A", "text": "hello", "links": []}


@pytest.fixture()
def web(client, monkeypatch):
    calls = []

    def fake(url):
        calls.append(url)
        return dict(PAGE, url=url)

    monkeypatch.setattr(websearch, "fetch_readable", fake)
    websearch._PREFETCHED.clear()
    return calls


def _rows():
    with deps.get_db().session() as session:
        return session.query(WebPage).all()


def test_a_chat_fetch_is_kept_with_its_time(web):
    websearch.fetch_readable_cached("https://example.org/a?utm_source=x")
    rows = _rows()
    assert len(rows) == 1 and rows[0].text == "hello"
    assert (utcnow() - rows[0].fetched_at) < timedelta(minutes=1)


def test_the_switch_off_keeps_nothing(web):
    deps.get_config().set_preference("web_store_enabled", False)
    websearch.fetch_readable_cached("https://example.org/a")
    assert _rows() == []


def test_a_second_fetch_updates_the_row_not_adds_one(web):
    websearch.fetch_readable_cached("https://example.org/a")
    websearch.fetch_readable_cached("https://example.org/a")
    assert len(_rows()) == 1


def test_pages_older_than_seven_days_are_dropped_on_the_next_keep(web):
    websearch.fetch_readable_cached("https://example.org/a")
    with deps.get_db().session() as session:
        session.query(WebPage).update({"fetched_at": utcnow() - timedelta(days=8)})
        session.commit()
    websearch.fetch_readable_cached("https://example.org/b")
    assert [r.url for r in _rows()] == ["https://example.org/b"]


def test_ages_names_kept_pages_only(client, web):
    websearch.fetch_readable_cached("https://example.org/a")
    body = client.post("/websearch/stored/ages", json={"urls": ["https://example.org/a", "https://example.org/zzz"]}).json()
    assert list(body["ages"]) == ["https://example.org/a"]


def test_refetch_updates_the_time_and_clear_empties(client, web):
    websearch.fetch_readable_cached("https://example.org/a")
    with deps.get_db().session() as session:
        session.query(WebPage).update({"fetched_at": utcnow() - timedelta(days=2)})
        session.commit()
    deps.get_config().set_preference("web_search_enabled", True)
    done = client.post("/websearch/stored/refetch", json={"url": "https://example.org/a"})
    assert done.status_code == 200 and (utcnow() - _rows()[0].fetched_at) < timedelta(minutes=1)
    cleared = client.delete("/websearch/stored")
    assert cleared.json() == {"cleared": 1}
    assert _rows() == []


def test_refetch_needs_web_search_on(client, web):
    deps.get_config().set_preference("web_search_enabled", False)
    refused = client.post("/websearch/stored/refetch", json={"url": "https://example.org/a"})
    assert refused.status_code == 403


def test_the_setting_and_the_controls_are_wired():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-web-store"' in html and 'id="web-store-clear"' in html
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "web_store_enabled", id: "pref-web-store" }' in rows
    kit = (ROOT / "frontend" / "js" / "answer-kit.js").read_text(encoding="utf-8")
    assert "/websearch/stored/ages" in kit and "Fetch again" in kit
    assert "Try again" in kit[kit.index("function toolChip") :]
