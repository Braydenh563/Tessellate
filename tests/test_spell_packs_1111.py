"""D30 (owner decision 2026-11-11): spelling for other languages comes as optional downloads.

Never vendored: Hunspell word lists are MPL or LGPL or GPL, and the repo takes AGPL or MIT only.
Each of French, German and Spanish is an extra in Settings, Packages (`core/extras.py`, the
download kind), fetched to the data dir on an Install click, sha256 checked, and served back to
the page from there. The page loads one lazily when a document's `lang` matches, in the Harper
worker, and the panel note for such a document offers the install through `extraNoticeMount`.
Every download here goes to a local fake file server; no test reaches the network.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from tessellate.core import extra_downloads, extras, spellpacks
from tests.test_extras_download import _Server, _wait

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


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WORKER = JS / "harper-worker.js"

#: A hand-written French dictionary, small enough to read: "cheval" takes the plural "x" of the
#: affix rule, so "chevaux" is a word only the affix file knows.
AFF = "SET UTF-8\nSFX X Y 1\nSFX X al aux al\n"
DIC = "4\nbonjour\ncheval/X\nécole\nmaison\n"


def _pack_tgz(aff: str = AFF, dic: str = DIC) -> bytes:
    """The npm tarball shape the pinned downloads use: `package/index.aff` and friends."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in {
            "package/index.aff": aff.encode(),
            "package/index.dic": dic.encode(),
            "package/license": b"MPL-2.0",
            "package/index.js": b"// never unpacked",
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _point_at(monkeypatch, extra_id: str, server: _Server, payload: bytes):
    extra = extras.EXTRAS_BY_ID[extra_id]
    (server.root / f"{extra_id}.tgz").write_bytes(payload)
    moved = dataclasses.replace(
        extra.downloads[0],
        url=f"{server.url}/{extra_id}.tgz",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )
    patched = dataclasses.replace(extra, downloads=(moved,))
    monkeypatch.setitem(extras.EXTRAS_BY_ID, extra_id, patched)
    monkeypatch.setattr(extras, "EXTRAS", tuple(patched if e.id == extra_id else e for e in extras.EXTRAS))
    return patched


# --- the catalogue ---------------------------------------------------------------------------


def test_french_german_and_spanish_are_download_extras_pinned_to_a_hash() -> None:
    rows = {e.id: e for e in extras.EXTRAS if e.id.startswith("spell-")}
    assert set(rows) == {"spell-fr", "spell-de", "spell-es"}
    for lang in ("fr", "de", "es"):
        extra = rows[f"spell-{lang}"]
        assert extra.kind == "download" and extra.version and extra.licence
        (download,) = extra.downloads
        assert download.url.startswith("https://") and re.fullmatch(r"[0-9a-f]{64}", download.sha256)
        assert download.unpack == "tar" and 0 < download.size < 2_000_000
        names = dict(download.members)
        assert names["package/index.aff"] == f"{lang}.aff"
        assert names["package/index.dic"] == f"{lang}.dic"
        assert "package/index.js" not in names, "only the dictionary files are kept"


def test_the_packs_are_never_in_the_repository() -> None:
    vendor = ROOT / "frontend" / "vendor"
    assert not [p for p in vendor.rglob("*") if re.fullmatch(r"(fr|de|es)[._-].*\.(aff|dic|txt)|(fr|de|es)\.(aff|dic)", p.name)]
    assert not [p for p in vendor.rglob("*.dic") if not re.match(r"en_", p.name)]


def test_listing_the_packs_touches_no_network(client, monkeypatch) -> None:
    def refuse(*_a, **_k):
        raise AssertionError("the network was touched without an install click")

    monkeypatch.setattr(extra_downloads, "_open_url", refuse)
    body = client.get("/spellpacks").json()
    assert [p["lang"] for p in body["packs"]] == ["fr", "de", "es"]
    for pack in body["packs"]:
        assert pack["installed"] is False and pack["id"] == f"spell-{pack['lang']}" and pack["name"]


def test_the_packages_card_names_where_it_downloads_from(client) -> None:
    rows = {e["id"]: e for e in client.get("/extras").json()["extras"]}
    for lang in ("fr", "de", "es"):
        row = rows[f"spell-{lang}"]
        assert row["kind"] == "download" and row["source"] == "registry.npmjs.org"
        assert row["licence"] and "this computer" in row["enables"]
        assert row["installed"] is False


# --- install, serve, offline ---------------------------------------------------------------


def test_install_downloads_to_the_data_dir_and_serves_the_files(client, monkeypatch, server) -> None:
    _point_at(monkeypatch, "spell-fr", server, _pack_tgz())
    assert client.get("/spellpacks/fr/aff").status_code == 404, "not installed yet"
    assert client.post("/extras/spell-fr/install").json()["started"] is True
    _wait()
    assert extras.current().outcome == "completed", extras.current().step

    folder = extra_downloads.folder(extras.EXTRAS_BY_ID["spell-fr"])
    assert (folder / "fr.aff").read_text(encoding="utf-8") == AFF
    assert not (folder / "index.js").exists()
    assert ROOT not in folder.parents, "the pack goes to the data dir, never the repo"

    packs = {p["lang"]: p for p in client.get("/spellpacks").json()["packs"]}
    assert packs["fr"]["installed"] is True and packs["de"]["installed"] is False
    aff, dic = client.get("/spellpacks/fr/aff"), client.get("/spellpacks/fr/dic")
    assert aff.status_code == dic.status_code == 200
    assert aff.text == AFF and dic.text == DIC
    assert aff.headers["content-type"].startswith("text/plain")
    server.close()
    assert client.get("/spellpacks/fr/dic").status_code == 200, "offline once installed"


def test_a_wrong_hash_installs_nothing(client, monkeypatch, server) -> None:
    patched = _point_at(monkeypatch, "spell-de", server, _pack_tgz())
    bad = dataclasses.replace(patched.downloads[0], sha256="0" * 64)
    monkeypatch.setitem(extras.EXTRAS_BY_ID, "spell-de", dataclasses.replace(patched, downloads=(bad,)))
    client.post("/extras/spell-de/install")
    _wait()
    assert extras.current().outcome != "completed"
    assert client.get("/spellpacks/de/aff").status_code == 404
    assert next(p for p in client.get("/spellpacks").json()["packs"] if p["lang"] == "de")["installed"] is False


@pytest.mark.parametrize("path", ["/spellpacks/en/aff", "/spellpacks/xx/dic", "/spellpacks/fr/js", "/spellpacks/..%2Fx/aff"])
def test_only_a_known_language_and_file_is_served(client, path) -> None:
    assert client.get(path).status_code == 404


def test_removing_the_pack_takes_the_files_away(client, monkeypatch, server) -> None:
    _point_at(monkeypatch, "spell-es", server, _pack_tgz())
    client.post("/extras/spell-es/install")
    _wait()
    assert spellpacks.installed("es")
    assert client.post("/extras/spell-es/uninstall").json()["started"] is True
    _wait()
    assert not spellpacks.installed("es")
    assert client.get("/spellpacks/es/aff").status_code == 404


# --- the worker -----------------------------------------------------------------------------

DRIVER = r"""
import { readFile } from "node:fs/promises";
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const href = String(url && url.href ? url.href : url);
  if (href.startsWith("file:")) {
    const type = href.endsWith(".wasm") ? "application/wasm" : "text/plain";
    return new Response(await readFile(new URL(href)), { headers: { "Content-Type": type } });
  }
  return realFetch(url, init);
};
let handler = null;
let replies = [];
globalThis.self = {
  addEventListener: (type, fn) => { if (type === "message") handler = fn; },
  postMessage: (message) => replies.push(message),
};
await import(process.argv[2]);
const jobs = JSON.parse(await readFile(process.argv[3], "utf8"));
const out = [];
for (const job of jobs) {
  replies = [];
  for (const message of job.messages) await handler({ data: message });
  out.push(replies);
}
process.stdout.write(JSON.stringify(out));
"""


def _worker(tmp_path: Path, jobs: list[dict]) -> list[list[dict]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script, jobs_file = tmp_path / "driver.mjs", tmp_path / "jobs.json"
    script.write_text(DRIVER, encoding="utf-8")
    jobs_file.write_text(json.dumps(jobs), encoding="utf-8")
    done = subprocess.run([node, str(script), WORKER.as_uri(), str(jobs_file)], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


def test_the_worker_spells_with_the_pack_it_was_given_and_suggests(tmp_path) -> None:
    load = {"id": 1, "type": "packload", "lang": "fr", "aff": AFF, "dic": DIC}
    ask = {"id": 2, "type": "packspell", "lang": "fr", "words": ["bonjour", "chevaux", "école", "Maison", "bonjuor", "xyzzy"]}
    (loaded, answered) = _worker(tmp_path, [{"messages": [load]}, {"messages": [ask]}])
    assert loaded[0]["ok"] is True
    spell = answered[0]["spell"]
    for word in ("bonjour", "chevaux", "école", "Maison"):
        assert spell[word]["known"] is True, word
    assert spell["bonjuor"]["known"] is False and "bonjour" in spell["bonjuor"]["suggestions"]
    assert spell["xyzzy"] == {"known": False, "suggestions": []}


def test_a_language_with_no_pack_loaded_answers_nothing_rather_than_flagging(tmp_path) -> None:
    (answered,) = _worker(tmp_path, [{"messages": [{"id": 1, "type": "packspell", "lang": "de", "words": ["Haus"]}]}])
    assert answered[0]["ok"] is True and answered[0]["spell"] == {}


def test_english_is_unchanged_by_the_pack_messages(tmp_path) -> None:
    (answered,) = _worker(tmp_path, [{"messages": [{"id": 1, "type": "spell", "dialect": "off", "words": ["colour", "teh"]}]}])
    assert answered[0]["spell"]["colour"]["known"] is True
    assert answered[0]["spell"]["teh"]["known"] is False
