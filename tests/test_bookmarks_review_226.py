"""Source text: the route is exercised through the test client; the front-end half has no browser under pytest, so its script is read as text.

Review 5883447855 on PR 226: the link list stays light, a fetch never overwrites a newer address,
only a save the person made in the app goes online by itself, and an icon fetch is small and quick.
"""

from __future__ import annotations

import threading

from tessellate.core import deps, webclip
from tessellate.core.database import Bookmark
from tests.test_webclip import FakeResponse, net, page  # noqa: F401  (net and page are fixtures)

ICON = "data:image/png;base64," + "A" * 40_000


def _join_icon_threads() -> None:
    for t in threading.enumerate():
        if t.name.startswith("bookmark-icon-"):
            t.join(5)


def test_the_list_of_300_links_carries_no_icon_bytes_or_page_text(client):
    session = deps.get_db().session()
    try:
        for i in range(300):
            session.add(Bookmark(url=f"https://site{i}.example/", title=f"Site {i}", favicon=ICON, page_text="word " * 4000))
        session.commit()
    finally:
        session.close()
    response = client.get("/bookmarks?limit=300")
    rows = response.json()
    assert len(rows) == 300
    #: 300 links with a 40 KB icon and 20 KB of text each was about 18 MB; the list now carries an address.
    assert len(response.content) < 150_000, len(response.content)
    first = rows[0]
    assert first["has_text"] is True and first["favicon"].startswith(f"/bookmarks/{first['id']}/icon")


def test_the_icon_is_served_on_its_own_with_caching_headers(client):
    session = deps.get_db().session()
    try:
        row = Bookmark(url="https://bread.example/", favicon="data:image/png;base64,iVBORw0KGgo=")
        session.add(row)
        session.commit()
        bid = row.id
    finally:
        session.close()
    response = client.get(f"/bookmarks/{bid}/icon")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert "max-age" in response.headers["cache-control"] and response.headers["etag"]
    assert response.headers["x-content-type-options"] == "nosniff"
    again = client.get(f"/bookmarks/{bid}/icon", headers={"If-None-Match": response.headers["etag"]})
    assert again.status_code == 304


def test_a_link_with_no_icon_has_none_to_serve(client):
    bid = client.post("/bookmarks", json={"url": "https://bread.example/"}).json()["id"]
    assert client.get(f"/bookmarks/{bid}/icon").status_code == 404
    assert client.get("/bookmarks").json()[0]["favicon"] == ""


def _slow_page_that_moves_the_link(bid_box):
    """A fetch during which the person changes the link's address (the race)."""

    def fetch(url):
        session = deps.get_db().session()
        try:
            session.get(Bookmark, bid_box[0]).url = "https://moved.example/"
            session.commit()
        finally:
            session.close()
        return {"html": page("news_article.html").decode("utf-8", "replace"), "url": url}

    return fetch


def test_a_refresh_that_finishes_after_an_address_change_keeps_nothing(client, app_state, monkeypatch):
    app_state.set_preference("web_search_enabled", True)
    bid = client.post("/bookmarks", json={"url": "https://bread.example/"}).json()["id"]
    monkeypatch.setattr(webclip, "fetch_page", _slow_page_that_moves_the_link([bid]))
    monkeypatch.setattr(webclip, "fetch_icon", lambda url: "data:image/png;base64,AAAA")
    reply = client.post(f"/bookmarks/{bid}/refresh")
    assert reply.status_code == 409
    row = client.get("/bookmarks").json()[0]
    assert row["url"] == "https://moved.example/" and row["favicon"] == "" and row["has_text"] is False


def test_the_fetch_after_a_save_drops_what_it_found_when_the_address_moved(client, app_state, monkeypatch):
    app_state.set_preference("web_search_enabled", True)
    box = [None]
    monkeypatch.setattr(webclip, "fetch_page", _slow_page_that_moves_the_link(box))
    monkeypatch.setattr(webclip, "fetch_icon", lambda url: "data:image/png;base64,AAAA")
    started = threading.Event()
    real_thread = __import__("tessellate.api.routes_bookmarks", fromlist=["jobs"]).jobs.thread

    def later(name, target):
        #: Hold the background fetch until the id is known, as a slow site would.
        def run():
            started.wait(5)
            target()

        return real_thread(name, run)

    monkeypatch.setattr("tessellate.api.routes_bookmarks.jobs.thread", later)
    made = client.post("/bookmarks", json={"url": "https://bread.example/", "fetch": True}).json()
    box[0] = made["id"]
    started.set()
    _join_icon_threads()
    row = client.get("/bookmarks").json()[0]
    assert row["url"] == "https://moved.example/" and row["favicon"] == "" and row["has_text"] is False


def test_a_save_over_the_api_without_the_flag_requests_nothing(client, app_state, net):  # noqa: F811
    #: An agent, the MCP server or a script saving a link never goes online by itself; the app's own
    #: Save sends `fetch: true` (the person pressed it with the web on).
    app_state.set_preference("web_search_enabled", True)
    names, pages, log = net
    for host in ("bread.example", "other.example"):
        names[host] = ["93.184.216.34"]
        pages[host] = FakeResponse(200, page("news_article.html"))
    made = client.post("/bookmarks", json={"url": "https://bread.example/"}).json()
    client.put(f"/bookmarks/{made['id']}", json={"url": "https://other.example/"})
    _join_icon_threads()
    assert log == []


def test_the_app_sends_the_fetch_flag_on_its_own_saves():
    from pathlib import Path

    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    #: The add form and the edit form (library.js), and Save on a web result (web-results.js, lazy).
    assert (js / "library.js").read_text().count("fetch: true") == 2
    assert "fetch: true" in (js / "web-results.js").read_text()


def test_an_icon_too_large_by_its_header_is_refused_before_reading(net):  # noqa: F811
    names, pages, _log = net
    names["x.example"] = ["93.184.216.34"]
    big = FakeResponse(200, b"0" * 10, {"content-type": "image/png", "content-length": str(webclip.ICON_MAX_BYTES + 1)})
    pages["x.example"] = big
    assert webclip.fetch_icon("https://x.example/f.png") == ""


def test_an_icon_fetch_has_its_own_short_deadline():
    assert webclip.ICON_DEADLINE_SECONDS <= 3 < webclip.CLIP_DEADLINE_SECONDS
