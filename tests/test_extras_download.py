"""The second kind of extra: a pinned download, checked and unpacked (INBOX 404, 302).

The owner, 2026-09-24: "Run Python files: yes, as an opt-in extra" and, for
needle, "Yes, as an extra". Neither is a pip package, so `core/extras.py`
grew a second kind: a pinned URL, a sha256, and an unpack step into the data
dir, behind the same routes and the same Settings row.

The properties held here are the whole safety case: the network is touched
only when Install is pressed, a file whose hash is not the pinned one is
refused and nothing of it is kept, an archive can only put the files the
entry names where the entry says, and the app is fully offline afterwards.
Every download goes to a local fake file server; no test reaches the network.
"""

from __future__ import annotations

import dataclasses
import hashlib
import http.server
import io
import re
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

from tessellate.core import extra_downloads, extras
from tests.native_binaries import elf64


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


class _Server:
    """A local file server over a temp folder, counting what it served."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.hits: list[str] = []
        outer = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def do_GET(self):  # noqa: N802  # the stdlib's name
                outer.hits.append(self.path)
                super().do_GET()

            def log_message(self, *args):  # quiet
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "served"
    root.mkdir()
    srv = _Server(root)
    yield srv
    srv.close()


def _tar_bz2(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:bz2") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buf.getvalue()


PYODIDE_FILES = {
    "pyodide/pyodide.mjs": b"export const loadPyodide = 1;",
    "pyodide/pyodide.asm.mjs": b"// asm",
    "pyodide/pyodide.asm.wasm": b"\0asm\1\0\0\0",
    "pyodide/python_stdlib.zip": b"PK",
    "pyodide/pyodide-lock.json": b"{}",
    "pyodide/package.json": b'{"license": "MPL-2.0"}',
    # In the real archive and never unpacked: nothing names it.
    "pyodide/python.exe": b"MZ",
}


def _point_at(monkeypatch, extra_id: str, server: _Server, payloads: dict[str, bytes], sha=None):
    """Re-pin `extra_id`'s downloads at the fake server, one payload per
    download in order, with the payload's real hash unless `sha` says
    otherwise."""
    extra = extras.EXTRAS_BY_ID[extra_id]
    wanted = extra_downloads.downloads_for(extra)
    new = []
    names = list(payloads)
    for i, download in enumerate(extra.downloads):
        if download not in wanted:
            new.append(download)
            continue
        name = names[wanted.index(download)]
        data = payloads[name]
        (server.root / name).write_bytes(data)
        new.append(
            dataclasses.replace(
                download,
                url=f"{server.url}/{name}",
                sha256=sha or hashlib.sha256(data).hexdigest(),
                size=len(data),
            )
        )
    patched = dataclasses.replace(extra, downloads=tuple(new))
    monkeypatch.setitem(extras.EXTRAS_BY_ID, extra_id, patched)
    monkeypatch.setattr(
        extras, "EXTRAS", tuple(patched if e.id == extra_id else e for e in extras.EXTRAS)
    )
    return patched


def _wait():
    deadline = time.time() + 20
    while extras.current().running and time.time() < deadline:
        time.sleep(0.02)
    assert not extras.current().running, "the install never finished"


def _row(client, extra_id):
    return next(e for e in client.get("/extras").json()["extras"] if e["id"] == extra_id)


# --- the catalogue ---------------------------------------------------------


def test_every_download_is_pinned_https_with_a_sha256_and_a_size():
    """A download extra is a URL, a hash and a size written down in the
    code. Nothing about it is looked up at run time."""
    found = 0
    for extra in extras.EXTRAS:
        if extra.kind != "download":
            continue
        assert extra.version and extra.licence, extra.id
        for download in extra.downloads:
            found += 1
            assert download.url.startswith("https://"), download.url
            assert re.fullmatch(r"[0-9a-f]{64}", download.sha256), download.url
            assert download.size > 0, download.url
            assert download.unpack in {"file", "tar", "zip", "gzip"}, download.url
            for _member, name in download.members:
                assert re.fullmatch(r"[A-Za-z0-9._-]+", name) and name not in {".", ".."}
    assert found >= 3


def test_python_and_needle_are_offered_as_download_extras(client):
    rows = {e["id"]: e for e in client.get("/extras").json()["extras"]}
    assert rows["pyodide"]["kind"] == "download"
    assert rows["needle"]["kind"] == "download"
    for row in (rows["pyodide"], rows["needle"]):
        assert row["installed"] is False
        assert row["source"], "the dialog says where it downloads from"
        assert row["licence"]
    assert rows["voice"]["kind"] == "pip"


def test_listing_the_extras_touches_no_network(client, monkeypatch):
    """Offline by default: the network is used by Install and nothing else."""

    def refuse(*_a, **_k):
        raise AssertionError("the network was touched without an install click")

    monkeypatch.setattr(extra_downloads, "_open_url", refuse)
    assert client.get("/extras").status_code == 200


# --- install, offline afterwards -----------------------------------------------


def test_install_downloads_checks_and_unpacks_then_works_offline(client, monkeypatch, server):
    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    body = client.post("/extras/pyodide/install").json()
    assert body["started"] is True, body
    _wait()
    assert extras.current().outcome == "completed", extras.current().step
    assert "restart" not in extras.current().step.lower()

    folder = extra_downloads.folder(extras.EXTRAS_BY_ID["pyodide"])
    assert (folder / "pyodide.mjs").read_bytes() == PYODIDE_FILES["pyodide/pyodide.mjs"]
    assert (folder / "pyodide.asm.wasm").is_file()
    assert not (folder / "python.exe").exists(), "only the named members are unpacked"
    assert server.hits == ["/core.tar.bz2"]

    # The server goes away: the extra is still installed, nothing asks again.
    server.close()
    assert _row(client, "pyodide")["installed"] is True
    assert extras.download_ready("pyodide") == folder


def test_a_hash_mismatch_is_refused_and_nothing_is_kept(client, monkeypatch, server):
    _point_at(
        monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)}, sha="0" * 64
    )
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "failed"
    assert "checksum" in extras.current().step.lower()
    root = extra_downloads.root_dir()
    assert not extra_downloads.folder(extras.EXTRAS_BY_ID["pyodide"]).exists()
    assert not [p for p in root.iterdir()] if root.exists() else True
    assert _row(client, "pyodide")["installed"] is False


def test_a_file_bigger_than_its_pin_is_cut_off(client, monkeypatch, server):
    extra = _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    small = dataclasses.replace(extra.downloads[0], size=10)
    monkeypatch.setitem(extras.EXTRAS_BY_ID, "pyodide", dataclasses.replace(extra, downloads=(small,)))
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "failed"
    assert "bigger" in extras.current().step.lower()


def test_an_archive_missing_a_named_file_is_refused(client, monkeypatch, server):
    partial = {k: v for k, v in PYODIDE_FILES.items() if not k.endswith(".wasm")}
    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(partial)})
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "failed"
    assert not extra_downloads.folder(extras.EXTRAS_BY_ID["pyodide"]).exists()


def test_a_member_name_cannot_climb_out_of_the_folder():
    """The names come from this file, but the check is the rule, not the
    catalogue's good behaviour."""
    for bad in ("../x", "a/b", "..", "", "x\\y"):
        with pytest.raises(ValueError):
            extra_downloads.Download(
                url="https://example.invalid/x", sha256="0" * 64, size=1, unpack="file",
                members=(("", bad),),
            )


def test_only_https_or_a_loopback_mirror_is_fetched():
    assert extra_downloads.url_allowed("https://github.com/x")
    assert extra_downloads.url_allowed("http://127.0.0.1:9/x")
    assert not extra_downloads.url_allowed("http://github.com/x")
    assert not extra_downloads.url_allowed("file:///etc/passwd")
    assert not extra_downloads.url_allowed("ftp://example.com/x")


def test_a_mirror_changes_only_the_address_never_the_hash(client, monkeypatch, server):
    """`TESSELLATE_EXTRAS_MIRROR` is for a machine with no internet (and for
    the browser sweep): the same file name from a local folder, still held to
    the pinned sha256."""
    archive = _tar_bz2(PYODIDE_FILES)
    extra = extras.EXTRAS_BY_ID["pyodide"]
    name = extra.downloads[0].url.rsplit("/", 1)[-1]
    (server.root / name).write_bytes(archive)
    pinned = dataclasses.replace(
        extra.downloads[0], sha256=hashlib.sha256(archive).hexdigest(), size=len(archive)
    )
    monkeypatch.setitem(extras.EXTRAS_BY_ID, "pyodide", dataclasses.replace(extra, downloads=(pinned,)))
    monkeypatch.setenv(extra_downloads.MIRROR_ENV, server.url + "/")
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "completed", extras.current().step
    assert server.hits == [f"/{name}"]

    # The same mirror with the real pin: a different file, refused.
    extras.reset_for_tests()
    monkeypatch.setitem(extras.EXTRAS_BY_ID, "pyodide", extra)
    extras.start("pyodide", reinstall=True)
    _wait()
    assert extras.current().outcome == "failed"


def test_a_mirror_must_be_https_or_this_machine(monkeypatch):
    extra = extras.EXTRAS_BY_ID["pyodide"]
    monkeypatch.setenv(extra_downloads.MIRROR_ENV, "http://example.com/files")
    url = extra_downloads.effective_url(extra.downloads[0])
    assert url.startswith("http://example.com/files/pyodide-core-")
    assert not extra_downloads.url_allowed(url)


def test_a_cancelled_download_keeps_nothing(client, monkeypatch, server):
    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})

    class Slow:
        def __init__(self):
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, _n):
            if self.sent:
                extras.cancel()
            self.sent = True
            return b"x"

    monkeypatch.setattr(extra_downloads, "_open_url", lambda url: Slow())
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "cancelled"
    assert not extra_downloads.folder(extras.EXTRAS_BY_ID["pyodide"]).exists()


def test_uninstall_removes_the_folder(client, monkeypatch, server):
    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    extras.start("pyodide")
    _wait()
    assert _row(client, "pyodide")["installed"] is True
    assert client.post("/extras/pyodide/uninstall").json()["started"] is True
    _wait()
    assert extras.current().outcome == "completed"
    assert not extra_downloads.folder(extras.EXTRAS_BY_ID["pyodide"]).exists()
    assert _row(client, "pyodide")["installed"] is False


def test_a_download_extra_never_reaches_pip(client, monkeypatch, server):
    """conftest's guard refuses pip; this asserts the download path does not
    even build a pip command."""
    monkeypatch.setattr(extras, "_pip_base_command", lambda: pytest.fail("pip was reached"))
    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "completed"


def test_the_install_reaches_the_task_history(client, monkeypatch, server):
    from tessellate.core import taskhistory

    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    extras.start("pyodide")
    _wait()
    # The worker lowers `running` first and writes the history row a few
    # statements later (`_run_download_install`'s finally block), so `_wait()`
    # returning does not mean the row exists yet: on a loaded machine the test
    # thread wins that gap. Poll for the row, with a ceiling far above the gap.
    deadline = time.time() + 30
    rows = taskhistory.recent()
    while not any("Python" in str(row) for row in rows) and time.time() < deadline:
        time.sleep(0.02)
        rows = taskhistory.recent()
    assert any("Python" in str(row) for row in rows), rows


# --- needle's platform gate -------------------------------------------------------


def test_needle_unpacks_the_engine_for_this_platform_only(client, monkeypatch, server):
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    wheel = _zip({"cactus/libcactus.so": elf64(["malloc", "free"], ["libc.so.6"]), "cactus_runtime-4.1.0.dist-info/METADATA": b"m"})
    _point_at(
        monkeypatch,
        "needle",
        server,
        {"engine.whl": wheel, "needle3.cact": b"weights", "LICENSE": b"Apache License"},
    )
    extras.start("needle")
    _wait()
    assert extras.current().outcome == "completed", extras.current().step
    folder = extra_downloads.folder(extras.EXTRAS_BY_ID["needle"])
    assert sorted(p.name for p in folder.iterdir() if p.name != extra_downloads.MARKER) == [
        "LICENSE", "libcactus.so", "needle3.cact",
    ]
    assert len(server.hits) == 3


def test_needle_is_not_offered_where_no_engine_is_built(client, monkeypatch):
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-mipsel")
    row = _row(client, "needle")
    assert row["unavailable"], "a platform with no engine must say so"
    assert "linux-mipsel" in row["unavailable"]
    started, message = extras.start("needle")
    assert started is False
    assert "linux-mipsel" in message


def test_every_needle_platform_names_an_engine_file():
    extra = extras.EXTRAS_BY_ID["needle"]
    keys = {d.platform for d in extra.downloads if d.platform}
    assert {"linux-x86_64", "macos-arm64", "windows-x86_64"} <= keys
    for download in extra.downloads:
        if download.platform:
            assert download.unpack == "zip"
            assert [name for _m, name in download.members][0].startswith("libcactus.")


def test_needle_engine_is_cactus_runtime_410_pinned_to_one_revision():
    extra = extras.EXTRAS_BY_ID["needle"]
    assert extra.version == "4.1.0" and extra.licence == "Apache-2.0"
    wheels = [d for d in extra.downloads if d.platform]
    assert len(wheels) == 8 and len({d.sha256 for d in wheels}) == 8
    for d in wheels:
        assert "/Cactus-Compute/cactus/resolve/4e822c9036be2eb0e47ef556df32a818bb1572ef/releases/4.1.0/python/" in d.url
        assert d.inspect_imports and d.members[0][0].startswith("cactus/libcactus.")
    assert {d.platform: d.members[0][1] for d in wheels}["windows-x86_64"] == "libcactus.dll"


# --- the engine is read for network code before it is kept (INBOX 699) -------------


def _install_needle_with(monkeypatch, server, engine: bytes):
    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    wheel = _zip({"cactus/libcactus.so": engine})
    _point_at(
        monkeypatch,
        "needle",
        server,
        {"engine.whl": wheel, "needle3.cact": b"weights", "LICENSE": b"Apache License"},
    )
    extras.start("needle")
    _wait()
    return extras.EXTRAS_BY_ID["needle"]


def test_needle_engine_that_imports_a_network_call_is_refused(client, monkeypatch, server):
    extra = _install_needle_with(monkeypatch, server, elf64(["malloc", "connect", "getaddrinfo"], ["libc.so.6"]))
    state = extras.current()
    assert state.outcome == "failed", state.step
    assert "contains network code" in state.step
    assert "connect" in "\n".join(state.log) and "getaddrinfo" in "\n".join(state.log)
    assert not extra_downloads.folder(extra).exists(), "nothing of a refused engine is kept"
    assert not extra_downloads.is_installed(extra)


def test_needle_engine_that_cannot_be_read_is_refused(client, monkeypatch, server):
    extra = _install_needle_with(monkeypatch, server, b"\x7fELF engine")
    state = extras.current()
    assert state.outcome == "failed"
    assert "could not be checked" in state.step
    assert not extra_downloads.folder(extra).exists()


def test_needle_engine_downloads_are_all_inspected_and_pinned_per_platform():
    extra = extras.EXTRAS_BY_ID["needle"]
    engines = [d for d in extra.downloads if d.platform]
    assert len(engines) == 8
    assert len({d.platform for d in engines}) == 8, "one engine per platform"
    for d in engines:
        assert d.inspect_imports, d.platform
        assert re.fullmatch(r"[0-9a-f]{64}", d.sha256), d.platform
        assert "/4e822c9036be2eb0e47ef556df32a818bb1572ef/" in d.url, "pinned to a commit"
    for d in extra.downloads:
        if not d.platform:
            assert re.fullmatch(r"[0-9a-f]{64}", d.sha256)


def test_needle_row_says_the_engine_is_checked_at_install():
    assert "checks at install" in extras.EXTRAS_BY_ID["needle"].caveat


def test_a_server_error_is_tried_again(client, monkeypatch, server):
    """GitHub's release downloads answer 504 now and then; one blip used to
    fail the whole install (the Windows package check, 2026-11-08)."""
    import urllib.error

    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    real = extra_downloads._open_url
    tries = []

    def flaky(url):
        tries.append(url)
        if len(tries) < 3:
            raise urllib.error.HTTPError(url, 504, "Gateway Time-out", {}, None)
        return real(url)

    monkeypatch.setattr(extra_downloads, "_open_url", flaky)
    monkeypatch.setattr(extra_downloads.time, "sleep", lambda _s: None)
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "completed", extras.current().log[-5:]
    assert len(tries) == 3
    assert any("answered 504" in line for line in extras.current().log)


def test_a_missing_file_is_not_tried_again(client, monkeypatch, server):
    import urllib.error

    _point_at(monkeypatch, "pyodide", server, {"core.tar.bz2": _tar_bz2(PYODIDE_FILES)})
    tries = []

    def gone(url):
        tries.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(extra_downloads, "_open_url", gone)
    monkeypatch.setattr(extra_downloads.time, "sleep", lambda _s: None)
    extras.start("pyodide")
    _wait()
    assert extras.current().outcome == "failed"
    assert len(tries) == 1


def test_the_captions_model_lands_as_the_one_file_the_helper_reads(client, monkeypatch, server):
    """INBOX 1777: the tiny.en file is a `file` download, hash checked, and
    `captions_process.model_path` finds it as an absolute path."""
    from tessellate.ai import captions_process

    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    _point_at(monkeypatch, "captionmodel", server, {"model.bin": b"ggml-bytes"})
    assert captions_process.model_path() is None
    assert client.post("/extras/captionmodel/install").json()["started"] is True
    _wait()
    assert extras.current().outcome == "completed", extras.current().step
    path = captions_process.model_path()
    assert path is not None and path.is_absolute()
    assert path.name == extras.CAPTIONS_MODEL_FILE and path.read_bytes() == b"ggml-bytes"
    assert _row(client, "captionmodel")["installed"] is True


def test_a_corrupt_captions_model_is_refused_and_not_kept(client, monkeypatch, server):
    from tessellate.ai import captions_process

    monkeypatch.setattr(extra_downloads, "platform_key", lambda: "linux-x86_64")
    _point_at(monkeypatch, "captionmodel", server, {"model.bin": b"ggml-bytes"}, sha="0" * 64)
    extras.start("captionmodel")
    _wait()
    assert extras.current().outcome == "failed" and "checksum" in extras.current().step.lower()
    assert captions_process.model_path() is None

