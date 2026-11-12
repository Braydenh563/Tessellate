"""Static files are compressed once per version, not on every fetch (INBOX 472).

`RevalidatedStatic._precompressed` in `api/app.py`: measured on loopback, the
448 KB stylesheet cost 22 to 46 ms gzipped on every request against 5 ms sent
as it is. These pin that the bytes are the file's (for the app's own scripts
and stylesheets, the file's with its comments stripped, audit 2026-10-05
FE-01, `tests/test_asset_strip.py`), that the cache is per version (an
edited file is compressed again), and that what the cache does not cover is
left exactly as it was.
"""

from __future__ import annotations

import gzip
import os

import pytest

from tessellate.api import app as app_module
from tessellate.api.app import FRONTEND_DIR, RevalidatedStatic
from tessellate.api.asset_strip import strip_css, strip_js


@pytest.fixture()
def cold(monkeypatch):
    """No in-memory copy from an earlier test in this process."""
    monkeypatch.setattr(RevalidatedStatic, "_gzip_cache", {})


def _app_js() -> bytes:
    return strip_js((FRONTEND_DIR / "js" / "app.js").read_text(encoding="utf-8")).encode()


def _raw(client, url, **headers):
    with client.stream("GET", url, headers=headers) as response:
        return response, b"".join(response.iter_raw())


def test_a_stylesheet_comes_back_as_its_own_bytes_gzipped(client, cold):
    response, raw = _raw(client, "/css/07-whiteboard-misc.css?v=1", **{"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.headers.get("etag")
    # The security headers are stamped on it like on every other response.
    assert "content-security-policy" in response.headers
    css = (FRONTEND_DIR / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert gzip.decompress(raw) == strip_css(css).encode()


def test_the_second_fetch_does_not_compress_again(client, cold, monkeypatch):
    calls = []
    real = gzip.compress
    monkeypatch.setattr(app_module.gzip, "compress", lambda *a, **k: calls.append(1) or real(*a, **k))
    for _ in range(3):
        _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    assert len(calls) <= 1


def test_a_new_process_reads_the_copy_on_disk(client, cold, monkeypatch, app_state):
    _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    folder = app_state.data_dir / "cache" / "static-gz"
    assert len(list(folder.glob("*.gz"))) == 1
    # A fresh process: the memory copy is gone, the disk one is not.
    monkeypatch.setattr(RevalidatedStatic, "_gzip_cache", {})
    monkeypatch.setattr(app_module.gzip, "compress", lambda *a, **k: pytest.fail("compressed again"))
    response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    assert gzip.decompress(raw) == _app_js()


def test_an_edited_file_is_compressed_again_and_its_old_copy_dropped(client, cold, app_state):
    path = FRONTEND_DIR / "js" / "app.js"
    _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    before = os.stat(path)
    try:
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
        assert gzip.decompress(raw) == _app_js()
        folder = app_state.data_dir / "cache" / "static-gz"
        names = [p.name for p in folder.glob("*.gz")]
        assert len(names) == 1 and str(before.st_mtime_ns + 1_000_000_000) in names[0]
    finally:
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))


def test_what_the_cache_does_not_cover_is_unchanged(client, cold):
    # No gzip asked for: the served bytes, not compressed.
    response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "identity"})
    assert "content-encoding" not in response.headers
    assert raw == _app_js()
    # A stripped file is one representation, served whole: a range request
    # for it gets all of it (a server may ignore Range), never a slice of
    # bytes no validator names.
    response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip", "Range": "bytes=0-9"})
    assert response.status_code == 200
    assert gzip.decompress(raw) == _app_js()
    # A file that is not stripped keeps its byte ranges.
    vendor = FRONTEND_DIR / "vendor" / "d3.v7.min.js"
    response, raw = _raw(
        client, "/vendor/d3.v7.min.js", **{"Accept-Encoding": "gzip", "Range": "bytes=0-9"}
    )
    assert response.status_code == 206
    assert raw == vendor.read_bytes()[:10]


def test_clearing_the_static_cache_empties_the_folder_and_the_memory_copy(
    client, cold, app_state
):
    """INBOX 487: Settings, Data, Clear app cache. Only the compressed copies
    go; the notebook (the database, uploads, backups) is not touched. The lock
    on the route is held by tests/test_every_route_is_locked.py, which walks
    every route."""
    _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    folder = app_state.data_dir / "cache" / "static-gz"
    assert list(folder.glob("*.gz"))
    assert RevalidatedStatic._gzip_cache
    neighbour = app_state.data_dir / "cache" / "keep.txt"
    neighbour.write_text("not ours")
    notebook = sorted(p.name for p in app_state.data_dir.iterdir())

    response = client.post("/system/clear-static-cache")
    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] is True and body["files"] >= 1
    assert list(folder.iterdir()) == []
    assert RevalidatedStatic._gzip_cache == {}
    assert neighbour.read_text() == "not ours"
    assert sorted(p.name for p in app_state.data_dir.iterdir()) == notebook
    # The next fetch compresses again and still answers.
    response, raw = _raw(client, "/js/app.js", **{"Accept-Encoding": "gzip"})
    assert gzip.decompress(raw) == _app_js()


def test_clearing_with_no_cache_folder_is_not_an_error(client, cold):
    response = client.post("/system/clear-static-cache")
    assert response.status_code == 200
    assert response.json() == {"cleared": True, "files": 0}
