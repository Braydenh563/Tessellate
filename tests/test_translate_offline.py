"""The offline translator (WORLD_CLASS_PLAN 28.5 row 10, Brief 83).

Bergamot and one language pair as an optional download in Settings,
Packages, never in the repository. The engine runs in the page's Worker;
the server says what is installed and serves the files by name from the
package's own list. Every download goes to a local fake file server.
"""

from __future__ import annotations

import gzip
import io
import tarfile
import time
from pathlib import Path

import pytest

from tessellate.ai import translate
from tessellate.core import extra_downloads, extras
from tessellate.core.security import build_csp
from tests.test_extras_download import _point_at, _Server

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "served"
    root.mkdir()
    srv = _Server(root)
    yield srv
    srv.close()


def _engine_tgz() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        for name, data in {
            "package/worker/bergamot-translator-worker.js": b"var Module;",
            "package/worker/bergamot-translator-worker.wasm": b"\0asm\1\0\0\0",
            "package/translator.js": b"// not kept",
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buf.getvalue()


PAYLOADS = {
    "engine.tgz": _engine_tgz(),
    "LICENSE": b"Mozilla Public License Version 2.0",
    "model.gz": gzip.compress(b"MODEL" * 100),
    "lex.gz": gzip.compress(b"LEX"),
    "vocab.gz": gzip.compress(b"VOCAB"),
}


def _install(client, monkeypatch, server) -> Path:
    _point_at(monkeypatch, "translate", server, PAYLOADS)
    started = client.post("/extras/translate/install").json()
    assert started["started"] is True
    deadline = time.time() + 20
    while extras.current().running and time.time() < deadline:
        time.sleep(0.02)
    assert extras.current().outcome == "completed", extras.current().step
    return extra_downloads.folder(extras.EXTRAS_BY_ID["translate"])


def test_the_package_is_a_pinned_mpl_download_never_in_the_repo():
    extra = extras.EXTRAS_BY_ID["translate"]
    assert extra.kind == "download" and extra.licence == "MPL-2.0"
    written = {name for d in extra.downloads for _m, name in d.members}
    assert set(translate.ENGINE_FILES) <= written
    assert "LICENSE" in written, "the MPL text travels with the engine"
    # The registry may name directions the package does not carry yet (L582);
    # each pair the package does write is a complete, registered row.
    carried = [p for p in translate.PAIRS if {p["model"], p["lex"], p["vocab"]} <= written]
    assert [(p["from"], p["to"]) for p in carried] == [("en", "es")]
    assert not {n for n in written if n.startswith("model.")} - {p["model"] for p in carried}
    assert any(extra.id in bundle.extras for bundle in extras.BUNDLES)
    assert not list((ROOT / "frontend").rglob("*.wasm.translate*"))
    assert not list(ROOT.glob("**/bergamot-translator-worker.*"))


def test_not_installed_says_so_and_names_settings_packages(client):
    body = client.get("/translate/status").json()
    assert body["installed"] is False and body["pairs"] == []
    assert "Settings, Packages" in body["hint"]
    missing = client.get("/translate/files/bergamot-translator-worker.wasm")
    assert missing.status_code == 404


def test_install_unpacks_the_gzipped_model_and_serves_only_listed_files(client, monkeypatch, server):
    folder = _install(client, monkeypatch, server)
    assert (folder / "model.enes.intgemm.alphas.bin").read_bytes() == b"MODEL" * 100
    assert not (folder / "translator.js").exists(), "only the named members are unpacked"

    body = client.get("/translate/status").json()
    assert body["installed"] is True and body["hint"] == ""
    assert body["pairs"][0]["from"] == "en" and body["pairs"][0]["to"] == "es"

    wasm = client.get("/translate/files/bergamot-translator-worker.wasm")
    assert wasm.status_code == 200 and wasm.headers["content-type"] == "application/wasm"
    js = client.get("/translate/files/bergamot-translator-worker.js")
    assert js.headers["content-type"].startswith("text/javascript")
    vocab = client.get("/translate/files/vocab.enes.spm")
    assert vocab.content == b"VOCAB"
    for name in ("installed.json", "..%2Finstalled.json", "translator.js"):
        refused = client.get(f"/translate/files/{name}")
        assert refused.status_code == 404, name


def test_the_files_need_no_token_but_the_status_does(client, monkeypatch, server):
    """A Worker's fetch carries no token, so the public engine and model are
    open; what is installed is behind the unlock like every other route."""
    from tessellate.api import routes_auth

    _install(client, monkeypatch, server)
    try:
        setup = client.post("/auth/setup", json={"password": "correct horse"})
        assert setup.status_code == 200
        licence = client.get("/translate/files/LICENSE")
        assert licence.status_code == 200
        locked = client.get("/translate/status")
        assert locked.status_code == 401
    finally:
        routes_auth._active_tokens.clear()


def test_a_bad_gzip_is_refused_and_nothing_is_kept(client, monkeypatch, server):
    bad = dict(PAYLOADS, **{"model.gz": b"not gzip at all"})
    _point_at(monkeypatch, "translate", server, bad)
    client.post("/extras/translate/install")
    deadline = time.time() + 20
    while extras.current().running and time.time() < deadline:
        time.sleep(0.02)
    assert extras.current().outcome == "failed"
    assert not extra_downloads.is_installed(extras.EXTRAS_BY_ID["translate"])


def test_the_app_policy_lets_the_worker_compile_webassembly():
    """Measured, not assumed: the engine needs `'wasm-unsafe-eval'` and a
    same-origin worker, and the glue needs no `eval`."""
    csp = build_csp([])
    assert "'wasm-unsafe-eval'" in csp and "'unsafe-eval'" not in csp.replace("'wasm-unsafe-eval'", "")
    assert "worker-src 'self'" in csp


def test_the_worker_and_the_palette_row_are_wired():
    worker = (JS / "translate-worker.js").read_text(encoding="utf-8")
    assert "/translate/files/" in worker and "importScripts" in worker
    sheet = (JS / "translate.js").read_text(encoding="utf-8")
    assert "translate-worker.js" in sheet and "/translate/status" in sheet
    #: Not installed: the one optional-package notice (Install, or Open Packages) replaced the
    #: toast and the jump to Settings; the intent, a way to the install, is unchanged.
    assert 'extraNoticeMount(slot, "translate"' in sheet
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8") + (JS / "app-features.js").read_text(encoding="utf-8")
    assert "Translate this" in panes
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert '"/js/translate.js"' in app
