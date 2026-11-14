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
from tests._app_js import documents_text

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
AFF = "SET UTF-8\nSFX X Y 1\nSFX X al aux al\nPFX L Y 1\nPFX L 0 l' .\n"
DIC = "11\nbonjour\ncheval/X\nécole\nmaison\nécurie/L\nle\nmonde\nest\ndans\nun\nnoir\n"


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
    assert loaded[0]["ok"] is True and loaded[0]["spell"] == {"loaded": True}
    spell = answered[0]["spell"]
    for word in ("bonjour", "chevaux", "école", "Maison"):
        assert spell[word]["known"] is True, word
    assert spell["bonjuor"]["known"] is False and "bonjour" in spell["bonjuor"]["suggestions"]
    assert spell["xyzzy"] == {"known": False, "suggestions": []}


def test_a_word_that_is_also_compound_only_is_still_a_word(tmp_path) -> None:
    """igerman98 lists "fahren" twice, once with ONLYINCOMPOUND; nspell merges the two entries and
    then refuses the word on its own (4.5% of the German stems measured). The worker drops the
    compound-only entry of a stem that has a plain one."""
    aff = "SET UTF-8\nONLYINCOMPOUND o\n"
    dic = "3\nfahren/o\nfahren/S\nhaus/o\n"
    ask = {"id": 2, "type": "packspell", "lang": "de", "words": ["fahren", "haus"]}
    (_, answered) = _worker(tmp_path, [{"messages": [{"id": 1, "type": "packload", "lang": "de", "aff": aff, "dic": dic}]}, {"messages": [ask]}])
    assert answered[0]["spell"]["fahren"]["known"] is True
    assert answered[0]["spell"]["haus"]["known"] is False, "a word only ever listed for compounds stays refused"


def test_a_language_with_no_pack_loaded_answers_nothing_rather_than_flagging(tmp_path) -> None:
    (answered,) = _worker(tmp_path, [{"messages": [{"id": 1, "type": "packspell", "lang": "de", "words": ["Haus"]}]}])
    assert answered[0]["ok"] is True and answered[0]["spell"] == {}


def test_english_is_unchanged_by_the_pack_messages(tmp_path) -> None:
    (answered,) = _worker(tmp_path, [{"messages": [{"id": 1, "type": "spell", "dialect": "off", "words": ["colour", "teh"]}]}])
    assert answered[0]["spell"]["colour"]["known"] is True
    assert answered[0]["spell"]["teh"]["known"] is False


# --- the page ---------------------------------------------------------------------------------

#: documents-spell.js run in node with the real worker behind `docGrammarSend` and the real
#: `docSpellable` and `docSpellNameKind` cut out of documents.js; the server and the DOM are stubs.
PAGE_DRIVER = r"""
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const [root, listFile] = process.argv.slice(2);
const scenario = JSON.parse(await readFile(listFile, "utf8"));
globalThis.fetch = async (url) => new Response(await readFile(new URL(url)), { headers: { "Content-Type": "text/plain" } });
let handler = null;
let replies = [];
globalThis.self = {
  addEventListener: (type, fn) => { if (type === "message") handler = fn; },
  postMessage: (message) => replies.push(message),
};
await import(pathToFileURL(`${root}/frontend/js/harper-worker.js`).href);
const documents = await readFile(`${root}/frontend/js/documents.js`, "utf8");
const cut = (name) => new RegExp(`^function ${name}\\b[\\s\\S]*?^\\}`, "m").exec(documents)[0];
const source = await readFile(`${root}/frontend/js/documents-spell.js`, "utf8");
let renders = 0;
let probes = 0;
const listeners = {};
const env = {
  window: { addEventListener: (type, fn) => { listeners[type] = fn; } },
  apiJson: async () => { probes += 1; return { packs: scenario.packs }; },
  api: async (url) => ({ text: async () => scenario.files[url] }),
  docGrammarEnabled: () => scenario.grammar !== false,
  docGrammarSend: async (message, reply = true) => {
    if (!reply) return null;
    replies = [];
    await handler({ data: { ...message, id: 1 } });
    const data = replies[0];
    return data.spell || data.lints || [];
  },
  renderDocProse: () => { renders += 1; },
  docSpellCache: new Map(),
  docDictionary: () => new Set(scenario.own || []),
  docProse: { langOf: () => "fr", langNote: () => "note" },
  extraNoticeMount: () => {},
  document: {},
};
const body = `${cut("docSpellable")}\n${cut("docSpellNameKind")}\n${source}\nreturn window.docSpell;`;
const docSpell = new Function(...Object.keys(env), body)(...Object.values(env));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const out = { steps: [] };
for (const step of scenario.steps) {
  const found = docSpell.packFindings(step.text, step.lang, () => false);
  await sleep(step.wait);
  out.steps.push({ found: found.map((f) => ({ text: f.text, alternatives: f.alternatives, message: f.message })), note: docSpell.packNote(step.lang), key: docSpell.packKey(), renders, probes });
}
if (scenario.event) { listeners["tessellate:extras-changed"](); await sleep(100); out.afterEvent = { probes, note: docSpell.packNote("fr") }; }
process.stdout.write(JSON.stringify(out));
"""


def _page(tmp_path: Path, scenario: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    driver, data = tmp_path / "page.mjs", tmp_path / "scenario.json"
    driver.write_text(PAGE_DRIVER, encoding="utf-8")
    data.write_text(json.dumps(scenario), encoding="utf-8")
    done = subprocess.run([node, str(driver), str(ROOT), str(data)], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


FILES = {"/spellpacks/fr/aff": AFF, "/spellpacks/fr/dic": DIC}
INSTALLED = [
    {"lang": "fr", "id": "spell-fr", "name": "French", "installed": True},
    {"lang": "de", "id": "spell-de", "name": "German", "installed": False},
]
TEXT = "Bonjour le monde. Un cheval noir est dans l'écurie. Un chevall noir est ici."


def test_a_french_document_is_checked_once_its_pack_has_loaded_and_answered(tmp_path) -> None:
    steps = [{"text": TEXT, "lang": "fr", "wait": 700}] * 4
    out = _page(tmp_path, {"packs": INSTALLED, "files": FILES, "steps": steps})
    first, second, third, fourth = out["steps"]
    # Each pass moves one stage (the page re-renders when each lands): the packs are listed, the
    # pack loads in the worker, the words are asked. Nothing is flagged until it has answered.
    assert first["found"] == [] and second["found"] == [] and third["found"] == []
    # By the fourth the words are answered: the ones that are not French are flagged, with fixes.
    third = fourth
    flagged = {f["text"]: f for f in third["found"]}
    assert set(flagged) == {"chevall", "ici"}, "ici is not in the small test dictionary; the rest are words"
    assert "cheval" in flagged["chevall"]["alternatives"]
    assert "French dictionary" in flagged["chevall"]["message"]
    assert third["note"] == "Spelling is checked in French from its installed pack. Grammar checks stay English."
    assert third["key"] > first["key"], "the rule memo's key moves with each answer"
    assert third["renders"] >= 3, "the page re-renders when the list, the load and the answers land"


def test_words_the_person_added_and_names_are_not_flagged(tmp_path) -> None:
    text = "Bonjour Priya. Un chevall est ici. Ensuite Marie ici."
    steps = [{"text": text, "lang": "fr", "wait": 700}] * 4
    out = _page(tmp_path, {"packs": INSTALLED, "files": FILES, "steps": steps, "own": ["chevall", "ici", "ensuite"]})
    assert out["steps"][3]["found"] == [], "Priya and Marie are names inside a sentence; the rest are the person's own words"


def test_a_language_without_an_installed_pack_is_never_flagged(tmp_path) -> None:
    out = _page(tmp_path, {"packs": INSTALLED, "files": FILES, "steps": [{"text": "Das Haus ist klein.", "lang": "de", "wait": 400}] * 2})
    for step in out["steps"]:
        assert step["found"] == [] and step["note"] == ""
    out = _page(tmp_path, {"packs": INSTALLED, "files": FILES, "steps": [{"text": "Hola mundo.", "lang": "es", "wait": 400}]})
    assert out["steps"][0]["found"] == [] and out["steps"][0]["note"] == ""


def test_an_install_elsewhere_is_seen_without_a_reload(tmp_path) -> None:
    missing = [{"lang": "fr", "id": "spell-fr", "name": "French", "installed": False}]
    out = _page(tmp_path, {"packs": missing, "files": FILES, "steps": [{"text": TEXT, "lang": "fr", "wait": 300}], "event": True})
    assert out["steps"][0]["found"] == [] and out["steps"][0]["note"] == ""
    assert out["afterEvent"]["probes"] == 2, "the extras-changed event asks the server again at once"


def test_with_the_grammar_checker_off_the_pack_is_not_started(tmp_path) -> None:
    out = _page(tmp_path, {"packs": INSTALLED, "files": FILES, "grammar": False, "steps": [{"text": TEXT, "lang": "fr", "wait": 500}] * 2})
    assert all(step["found"] == [] and step["note"] == "" for step in out["steps"])


# --- the wiring ---------------------------------------------------------------------------------

DOCUMENTS = documents_text()
SPELL = (JS / "documents-spell.js").read_text(encoding="utf-8")
NOTICE = (JS / "extra-notice.js").read_text(encoding="utf-8")


def test_the_pack_findings_join_the_prose_pass_for_a_non_english_document_only() -> None:
    assert "if (!english) found.push(...docSpell.packFindings(text, lang, skipped));" in DOCUMENTS
    assert "function docProseFindings(text, lang = docProse.langOf(text))" in DOCUMENTS
    # A paragraph passed alone has no frontmatter: the caller hands its document's language down.
    assert "docProseFindings(part, docProse.langOf(part))" in DOCUMENTS
    assert "docProseFindings(zone, docProse.langOf(part))" in DOCUMENTS
    assert "docSpell.packKey()" in DOCUMENTS, "the rule memo must know when a pack answer arrives"


def test_the_panel_note_offers_the_install_through_the_shared_notice() -> None:
    assert "Spelling and grammar are off for this document" in DOCUMENTS
    assert DOCUMENTS.count("docSpell.langRow(docText())") == 2, "both the empty and the listed panel"
    # Not `fresh`: the row is rebuilt on every panel redraw, so a fresh read was a GET /extras per redraw.
    assert "extraNoticeMount(slot, `spell-${lang}`)" in SPELL
    assert "`spell-${lang}`, { fresh: true }" not in SPELL
    for lang in ("fr", "de", "es"):
        assert f'"spell-{lang}":' in NOTICE
    assert "tessellate:extras-changed" in NOTICE and "tessellate:extras-changed" in SPELL
