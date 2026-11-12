"""INBOX 827 L3, L5 and the owner's stale-icon bug: a link keeps a look (icon, colour) and what the last
fetch found (the site's icon as a data address, an excerpt, the page text).

The network is the fake the clipper's tests use; nothing is requested while the web is off.
"""

from __future__ import annotations

import pytest

from tessellate.core import webclip
from tests.test_webclip import FakeResponse, FakeSession, net, page  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _make(client, **extra):
    return client.post("/bookmarks", json={"url": "https://bread.example/2026/sourdough", **extra}).json()


def test_a_link_takes_an_icon_and_a_colour(client):
    made = _make(client, icon="ph:star", color="blue")
    assert (made["icon"], made["color"]) == ("ph:star", "blue")
    changed = client.put(f"/bookmarks/{made['id']}", json={"icon": "\U0001F35E", "color": "orange"}).json()
    assert (changed["icon"], changed["color"]) == ("\U0001F35E", "orange")
    assert client.put(f"/bookmarks/{made['id']}", json={"icon": "", "color": ""}).json()["icon"] == ""
    assert client.get("/bookmarks").json()[0]["id"] == made["id"]


@pytest.mark.parametrize("body", [{"color": "chartreuse"}, {"icon": "<img src=x>"}, {"icon": "javascript"}, {"icon": "ph:Star Bad"}])
def test_a_look_outside_the_palette_is_refused(client, body):
    made = _make(client)
    assert client.put(f"/bookmarks/{made['id']}", json=body).status_code == 422


def test_refresh_is_refused_while_the_web_is_off(client, net):  # noqa: F811
    _names, _pages, log = net
    made = _make(client)
    response = client.post(f"/bookmarks/{made['id']}/refresh")
    assert response.status_code == 403 and "Web search" in response.json()["detail"]
    assert log == [], "nothing was fetched"


def _site(net, icon_type="image/png"):  # noqa: F811
    names, pages, _log = net
    names["bread.example"] = ["93.184.216.34"]
    html = page("news_article.html")
    html = html.replace(b"</head>", b'<link rel="icon" href="/fav.png"></head>', 1)
    pages["bread.example"] = FakeResponse(200, html)
    return pages


def test_refresh_keeps_the_icon_excerpt_and_text(client, app_state, net, monkeypatch):  # noqa: F811
    app_state.set_preference("web_search_enabled", True)
    _site(net)
    monkeypatch.setattr(webclip, "fetch_icon", lambda url: "data:image/png;base64,AAAA")
    made = _make(client)
    out = client.post(f"/bookmarks/{made['id']}/refresh").json()
    assert out["favicon"] == "data:image/png;base64,AAAA"
    assert out["excerpt"] and len(out["excerpt"]) <= 400 and out["has_text"] is True
    assert out["title"], "a link saved with no title takes the page's"
    assert client.get(f"/bookmarks/{made['id']}/text").json()["text"]
    assert "page_text" not in client.get("/bookmarks").json()[0], "the list stays light"


def test_a_named_link_keeps_its_name_and_a_new_address_drops_the_old_icon(client, app_state, net, monkeypatch):  # noqa: F811
    app_state.set_preference("web_search_enabled", True)
    _site(net)
    monkeypatch.setattr(webclip, "fetch_icon", lambda url: "data:image/png;base64,AAAA")
    made = _make(client, title="My bread")
    assert client.post(f"/bookmarks/{made['id']}/refresh").json()["title"] == "My bread"
    moved = client.put(f"/bookmarks/{made['id']}", json={"url": "https://other.example/"}).json()
    assert (moved["favicon"], moved["excerpt"], moved["has_text"]) == ("", "", False)
    same = client.put(f"/bookmarks/{made['id']}", json={"title": "Bread"}).json()
    assert same["favicon"] == "", "an edit that leaves the address alone does not touch the fetch"


def test_the_icon_href_is_read_from_the_page_and_defaults_to_favicon_ico():
    html = '<head><link rel="stylesheet" href="/a.css"><link rel="shortcut icon" href="img/i.png"></head>'
    assert webclip.page_icon_href(html, "https://x.example/blog/post") == "https://x.example/blog/img/i.png"
    assert webclip.page_icon_href("<head></head>", "https://x.example/a/b") == "https://x.example/favicon.ico"
    assert webclip.page_icon_href('<link rel="icon" href="javascript:alert(1)">', "https://x.example/") == ""


def test_fetch_icon_keeps_a_small_image_and_refuses_the_rest(net):  # noqa: F811
    names, pages, _log = net
    names["x.example"] = ["93.184.216.34"]
    pages["x.example"] = FakeResponse(200, PNG, {"content-type": "image/png"})
    assert webclip.fetch_icon("https://x.example/f.png").startswith("data:image/png;base64,")
    pages["x.example"] = FakeResponse(200, PNG, {"content-type": "text/html"})
    assert webclip.fetch_icon("https://x.example/f.png") == ""
    pages["x.example"] = FakeResponse(200, b"0" * (webclip.ICON_MAX_BYTES + 1), {"content-type": "image/png"})
    assert webclip.fetch_icon("https://x.example/f.png") == ""
    pages["x.example"] = FakeResponse(404, b"", {"content-type": "image/png"})
    assert webclip.fetch_icon("https://x.example/f.png") == ""
