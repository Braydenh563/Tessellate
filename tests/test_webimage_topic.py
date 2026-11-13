"""A topic's picture from a link (MINDMAP gap 8, XMind "insert image from URL").

Fetched once on the person's say-so, behind the web opt-in, through the clipper's
checked hops (private addresses refused at every hop), kept through the one
upload path (`/media/upload`, as a board-only picture). The network is a fake.
"""

from __future__ import annotations

import pytest

from tessellate.core import security, webclip, webimage
from tests.test_webclip import FakeResponse, FakeSession

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def net(monkeypatch):
    names: dict[str, list[str]] = {}
    pages: dict[str, FakeResponse] = {}
    log: list = []
    monkeypatch.setattr(security, "_resolve", lambda host: names.get(host, []))
    monkeypatch.setattr(webclip, "_new_session", lambda: FakeSession(pages, log))
    names["pics.example"] = ["93.184.216.34"]
    return names, pages, log


def _image(body=PNG, kind="image/png", **headers):
    return FakeResponse(200, body, {"content-type": kind, **headers})


def test_a_public_image_is_returned_with_its_suffix(net):
    _names, pages, _log = net
    pages["pics.example"] = _image()
    got = webimage.fetch_image("https://pics.example/a.png?utm_source=x")
    assert got["body"] == PNG and got["suffix"] == ".png"


@pytest.mark.parametrize("kind", ["image/svg+xml", "text/html", "application/pdf", "image/x-icon"])
def test_only_raster_picture_types_are_kept(net, kind):
    pages = net[1]
    pages["pics.example"] = _image(kind=kind)
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("https://pics.example/a")


def test_a_picture_past_the_size_cap_is_refused_by_header_and_by_stream(net, monkeypatch):
    pages = net[1]
    monkeypatch.setattr(webimage, "IMAGE_MAX_BYTES", 100)
    pages["pics.example"] = _image(**{"content-length": "5000"})
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("https://pics.example/big")
    pages["pics.example"] = _image(PNG + b"\x00" * 500)
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("https://pics.example/liar")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://pics.example/a.png", "http://u:p@pics.example/a.png"])
def test_only_plain_http_is_fetched(net, url):
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image(url)
    assert net[2] == []


def test_a_private_address_and_a_redirect_into_one_are_refused(net):
    names, pages, log = net
    names["lan.example"] = ["192.168.1.9"]
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("http://lan.example/a.png")
    pages["pics.example"] = FakeResponse(302, headers={"location": "http://lan.example/a.png"})
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("http://pics.example/a.png")
    assert [host for _u, host in log] == ["pics.example"]


def test_the_route_is_refused_while_the_web_is_off(client, net):
    response = client.post("/links/image", json={"url": "https://pics.example/a.png"})
    assert response.status_code == 403 and "Web search" in response.json()["detail"]
    assert net[2] == []


def test_the_route_keeps_it_as_a_board_only_upload(client, app_state, net):
    app_state.set_preference("web_search_enabled", True)
    net[1]["pics.example"] = _image()
    response = client.post("/links/image", json={"url": "https://pics.example/a.png"})
    assert response.status_code == 201, response.text
    out = response.json()
    assert out["url"].startswith("/media/") and out["url"].endswith(".png")
    listed = client.get("/media").json()
    assert all(item["id"] != out["id"] for item in (listed if isinstance(listed, list) else listed.get("items", []))), "a board picture is not in the Library"


def test_the_route_says_why_a_non_picture_is_not_kept(client, app_state, net):
    app_state.set_preference("web_search_enabled", True)
    net[1]["pics.example"] = _image(kind="text/html")
    response = client.post("/links/image", json={"url": "https://pics.example/page"})
    assert response.status_code == 400 and "picture" in response.json()["detail"]


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (b"<html><script>alert(1)</script></html>", "image/png"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 32, "image/png"),
        (PNG, "image/gif"),
        (b"", "image/jpeg"),
    ],
)
def test_bytes_that_are_not_the_declared_picture_are_refused(net, body, kind):
    """The review on PR 229: Content-Type is the server's word, so the bytes'
    own signature must match it before the picture is kept."""
    net[1]["pics.example"] = _image(body, kind)
    with pytest.raises(webclip.ClipRefused):
        webimage.fetch_image("https://pics.example/a")


@pytest.mark.parametrize(
    ("body", "kind", "suffix"),
    [
        (b"\xff\xd8\xff\xe0" + b"\x00" * 32, "image/jpeg", ".jpg"),
        (b"GIF89a" + b"\x00" * 32, "image/gif", ".gif"),
        (b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 16, "image/webp", ".webp"),
        (b"\x00\x00\x00\x1cftypavif" + b"\x00" * 16, "image/avif", ".avif"),
        (b"BM" + b"\x00" * 32, "image/bmp", ".bmp"),
    ],
)
def test_each_kept_kind_passes_on_its_own_signature(net, body, kind, suffix):
    net[1]["pics.example"] = _image(body, kind)
    assert webimage.fetch_image("https://pics.example/a")["suffix"] == suffix
