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


def test_a_file_that_throws_does_not_stop_the_files_after_it(tmp_path, monkeypatch):
    """L-documents-119: a classic script that throws stops the rest of that
    script, so the bundle records the last file that finished (on app.js's
    `lazyFileLoads` map) and `ensureModule` loads the files after the faulty
    one apart. Here the real bundle builder serves three files, the second
    throws, and node runs the result the way a page would."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    from tessellate.api import app as api_app

    (tmp_path / "js").mkdir()
    for name, body in (("a", "ran.push('a');"), ("b", "throw new Error('b');"), ("c", "ran.push('c');")):
        (tmp_path / "js" / f"{name}.js").write_text(body + "\n", encoding="utf-8")
    monkeypatch.setattr(api_app, "FRONTEND_DIR", tmp_path)
    monkeypatch.setattr(api_app, "library_bundle_files", lambda: ["/js/a.js", "/js/b.js", "/js/c.js"])
    monkeypatch.setattr(api_app, "_library_bundle_cache", {})
    body = api_app.library_bundle()[1].decode()
    script = (
        "const vm = require('vm');"
        "const lazyFileLoads = new Map(); const ran = [];"
        f"const code = {json.dumps(body)};"
        "try { vm.runInNewContext(code, {lazyFileLoads, ran}); } catch (e) {}"
        "console.log(JSON.stringify({at: lazyFileLoads.get('#at'), ran}));"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    # File 1 (b) threw: the marker counts one file finished, and c never ran.
    assert out == {"at": 1, "ran": ["a"]}
    # The page resumes after the faulty file: the count plus 1 is c.
    assert '"#at") + 1 || 0' in (APP_JS.parent / "documents-warm.js").read_text(encoding="utf-8")
