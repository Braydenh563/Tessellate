"""`/js/library-bundle.js` is the Library bundle's scripts as one served file
(L-documents-83, 106): the same bytes the 35 separate files serve, in the
order app.js's `LAZY_MODULES.library` lists them, so one request and one
parse replace 35. The list is read from app.js here by a different rule than
the server's (every quoted `/js/` path in the block), so a drift in either
shows."""

from __future__ import annotations

import re

from tessellate import __version__
from tests._app_js import APP_JS


def _listed() -> list[str]:
    text = APP_JS.read_text(encoding="utf-8")
    block = text[text.index("\n  library: [") : text.index("\n  ],", text.index("\n  library: ["))]
    return [
        name
        for line in block.splitlines()
        if (name := (re.match(r'\s*"(/js/[^"]+)"', line) or [None, None])[1])
        and name != "/js/documents-warm.js"
    ]


def _plain(client, path: str) -> bytes:
    response = client.get(path, headers={"Accept-Encoding": "identity"})
    assert response.status_code == 200
    return response.content


def test_the_bundle_is_the_separate_files_in_order(client):
    names = _listed()
    assert len(names) > 30
    served = _plain(client, "/js/library-bundle.js").decode()
    at = 0
    for name in names:
        part = _plain(client, name).decode()
        found = served.find(part, at)
        assert found >= 0, f"{name} is missing or out of order in the bundle"
        at = found + len(part)
    assert served.count("\n") >= sum(_plain(client, n).count(b"\n") for n in names)


def test_the_bundle_is_stamped_immutable_and_gzipped(client):
    response = client.get(
        f"/js/library-bundle.js?v={__version__}", headers={"Accept-Encoding": "gzip"}
    )
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.content == _plain(client, "/js/library-bundle.js")
    bare = client.get("/js/library-bundle.js", headers={"Accept-Encoding": "gzip"})
    assert bare.headers["cache-control"] == "no-cache"


def test_the_page_carries_the_bundles_own_stamp(client):
    page = client.get("/").text
    listed = re.search(r'name="asset-stamps" content="([^"]*)"', page).group(1)
    assert re.search(r"/js/library-bundle\.js=" + re.escape(__version__) + r"-[0-9a-f]{10}", listed)
