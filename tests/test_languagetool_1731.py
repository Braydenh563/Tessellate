"""LanguageTool as an optional download (INBOX 1731 (f)).

The owner, 2026-11-10: "can we like incorporate all of it or whatever you
suggest??". Every test runs against a fake file server and a fake local
LanguageTool; the real 6.6 archive's size and sha256 were read from
languagetool.org when the entry was written, but the real program was not
started here (real checking is unverified).
"""

from __future__ import annotations

import http.server
import json
import subprocess
import threading
import urllib.parse
from pathlib import Path

from tessellate.core import extra_downloads, extras, languagetool, languagetool_files
from tests.test_extras_download import _clean_extras, _point_at, _row, _wait, _zip, server  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def _archive() -> bytes:
    files = {src: b"PK-jar" for src, _name in languagetool_files.MEMBERS}
    files[languagetool_files.PREFIX + "org/languagetool/language-x/Lang.class"] = b"c"
    files[languagetool_files.PREFIX + "org/languagetool/language-x/Inner$1.class"] = b"c"
    files[languagetool_files.PREFIX + "META-INF/org/languagetool/language-module.properties"] = b"p"
    return _zip(files)


def test_the_entry_is_pinned_and_keeps_only_jars_and_the_licence():
    extra = extras.EXTRAS_BY_ID["languagetool"]
    (download,) = extra.downloads
    assert download.url.startswith("https://languagetool.org/download/LanguageTool-")
    assert len(download.sha256) == 64
    names = [name for _src, name in languagetool_files.MEMBERS]
    assert len(names) == len(set(names))
    assert {"languagetool.jar", "languagetool-server.jar", "COPYING.txt"} <= set(names)
    assert all(n.endswith(".jar") or n == "COPYING.txt" for n in names)
    assert extra.licence == "LGPL-2.1"


def test_listing_and_status_never_start_java_or_the_network(client, monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("started a process")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    assert _row(client, "languagetool")["installed"] is False
    reply = client.post("/grammar/languagetool", json={"text": "He go home."}).json()
    assert reply == {"available": False, "matches": []}


def test_without_java_the_install_is_refused_with_the_reason(client, monkeypatch):
    monkeypatch.setattr(languagetool_files, "java_path", lambda: None)
    assert "Java" in _row(client, "languagetool")["unavailable"]
    started = client.post("/extras/languagetool/install").json()["started"]
    assert started is False


def test_install_unpacks_flat_jars_then_the_check_is_available(client, monkeypatch, server):  # noqa: F811
    monkeypatch.setattr(languagetool_files, "java_path", lambda: "/usr/bin/java")
    _point_at(monkeypatch, "languagetool", server, {"lt.zip": _archive()})
    started = client.post("/extras/languagetool/install").json()["started"]
    assert started is True
    _wait()
    assert extras.current().outcome == "completed", extras.current().step
    folder = extra_downloads.folder(extras.EXTRAS_BY_ID["languagetool"])
    assert (folder / "languagetool-server.jar").is_file()
    #: The language modules are folders on the class path, kept with their paths (measured
    #: 2026-11-14: with the jars alone the real server died at start).
    assert (folder / "org/languagetool/language-x/Inner$1.class").is_file()
    assert (folder / "META-INF/org/languagetool/language-module.properties").is_file()
    assert all(p.parent == folder for p in folder.glob("*") if p.is_file())
    assert languagetool.available()


def test_a_tree_path_that_climbs_out_is_refused(tmp_path):
    import zipfile

    from tessellate.core.extra_downloads import DownloadFailed, _unpack_tree

    path = tmp_path / "a.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("P/org/../../evil.txt", b"x")
    staging = tmp_path / "s"
    staging.mkdir()
    with zipfile.ZipFile(path) as archive:
        try:
            _unpack_tree(archive, "P/org/", "org", staging)
        except DownloadFailed:
            pass
        else:
            raise AssertionError("a `..` part was kept")
    assert not (tmp_path / "evil.txt").exists()


def test_the_server_is_started_with_the_folder_on_its_class_path(monkeypatch, tmp_path):
    seen = {}

    def fake_popen(command, **_kw):
        seen["command"] = command
        raise OSError("stop here")

    monkeypatch.setattr(languagetool, "installed_folder", lambda: tmp_path)
    monkeypatch.setattr(languagetool, "java_path", lambda: "/usr/bin/java")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        languagetool._start()
    except OSError:
        pass
    classpath = seen["command"][seen["command"].index("-cp") + 1]
    assert str(tmp_path) in classpath.split(languagetool.os.pathsep)


class _Fake(http.server.BaseHTTPRequestHandler):
    seen: list[dict] = []

    def do_POST(self):  # noqa: N802  # the stdlib's name
        form = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        _Fake.seen.append(form)
        agreement = {
            "offset": 3,
            "length": 2,
            "message": "Agreement",
            "rule": {"id": "HE_VERB_AGR"},
        }
        agreement["replacements"] = [{"value": "goes"}]
        outside = {"offset": 99, "length": 2, "message": "outside", "rule": {"id": "X"}}
        body = json.dumps({"matches": [agreement, outside]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_check_shapes_matches_and_switches_spelling_off(monkeypatch):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(languagetool, "available", lambda: True)
    monkeypatch.setattr(languagetool, "_running_port", lambda: httpd.server_port)
    try:
        matches = languagetool.check("He go home.", "en-AU")
        languagetool.check("He go home.", "xx-YY")
    finally:
        httpd.shutdown()
        languagetool.stop()
    assert matches == [
        {
            "start": 3,
            "end": 5,
            "message": "Agreement",
            "rule": "HE_VERB_AGR",
            "suggestions": ["goes"],
        }
    ]
    assert _Fake.seen[0]["language"] == ["en-AU"] and _Fake.seen[0]["disabledCategories"] == [
        "TYPOS"
    ]
    assert _Fake.seen[1]["language"] == ["en-US"], "an unknown language asks for US English"


def test_the_program_listens_on_loopback_only(monkeypatch, tmp_path):
    seen = {}

    class _Process:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    def popen(command, **_kw):
        seen["command"] = command
        return _Process()

    monkeypatch.setattr(languagetool, "installed_folder", lambda: tmp_path)
    monkeypatch.setattr(languagetool, "java_path", lambda: "java")
    monkeypatch.setattr(languagetool, "_ready", lambda port: True)
    monkeypatch.setattr(subprocess, "Popen", popen)
    try:
        port = languagetool._start()
    finally:
        languagetool.stop()
    assert port
    assert "--public" not in seen["command"] and seen["command"][0] == "java"


def test_a_system_proxy_never_sees_the_text(monkeypatch):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setattr(languagetool, "available", lambda: True)
    monkeypatch.setattr(languagetool, "_running_port", lambda: httpd.server_port)
    try:
        assert languagetool.check("He go home.") is not None
    finally:
        httpd.shutdown()
        languagetool.stop()


def test_the_page_merges_without_duplicating_a_harper_span():
    script = r"""
    global.window = {docSpell: {}}; global.$ = () => null; global.docSpellingVariant = () => "au";
    let sent;
    global.apiJson = async (u, o) => { sent = JSON.parse(o.body);
      return {available: true, matches: [{start: 0, end: 4, message: "m", suggestions: ["a"]}, {start: 10, end: 12, message: "n", suggestions: []}]}; };
    eval(require("fs").readFileSync(process.argv[1], "utf8"));
    window.docSpell.languageTool([{kind: "Agreement", start: 2, end: 6}], "x".repeat(20)).then((r) => {
      console.log(JSON.stringify({n: r.length, kinds: r.map((l) => l.kind), lang: sent.language}));
    });
    """
    path = str(ROOT / "frontend/js/documents-languagetool.js")
    out = subprocess.run(["node", "-e", script, path], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == {
        "n": 2,
        "kinds": ["Agreement", "LanguageTool"],
        "lang": "en-AU",
    }


def test_a_second_check_sends_only_the_paragraphs_touched_and_maps_them_back():
    script = r"""
    global.window = {docSpell: {}}; global.$ = () => null; global.docSpellingVariant = () => "us";
    const sent = [];
    global.apiJson = async (u, o) => { const b = JSON.parse(o.body); sent.push(b.text);
      return {available: true, matches: [...b.text.matchAll(/bad/g)].map((m) => ({start: m.index, end: m.index + 3, message: "m", suggestions: []}))}; };
    eval(require("fs").readFileSync(process.argv[1], "utf8"));
    const one = "bad one\n\nfine two\nbad three";
    const two = "bad one\n\nfine two edited\nbad three";
    const lt = window.docSpell.languageTool;
    (async () => {
      const a = await lt([], one);
      const b = await lt([], two);
      console.log(JSON.stringify({sent, a: a.map((l) => l.start), b: b.map((l) => l.start)}));
    })();
    """
    path = str(ROOT / "frontend/js/documents-languagetool.js")
    out = subprocess.run(["node", "-e", script, path], capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    assert got["sent"] == ["bad one\n\nfine two\nbad three", "fine two edited"]
    assert got["a"] == [0, 18]
    assert got["b"] == [0, 25]


def test_only_english_data_is_kept_but_every_language_class_and_the_identifier_words(tmp_path):
    """L-documents-110: 392 MB on disk before, 196 MB with the real server started."""
    import zipfile

    from tessellate.core.extra_downloads import _unpack_tree

    p = languagetool_files.PREFIX + "org/languagetool/"
    kept = ["resource/en/x.dict", "resource/de/common_words.txt", "rules/de/Rule.class",
            "rules/en/grammar.xml", "rules/Rule.class", "language/German.class", "rules/pt-BR/A.class"]
    dropped = ["resource/de/german.dict", "resource/pt/hunspell/a.dic", "rules/de/grammar.xml",
               "rules/pt-BR/grammar.xml"]
    path = tmp_path / "a.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name in kept + dropped:
            archive.writestr(p + name, b"x")
    staging = tmp_path / "s"
    staging.mkdir()
    with zipfile.ZipFile(path) as archive:
        _unpack_tree(archive, languagetool_files.PREFIX + "org/", "org", staging,
                     languagetool_files.TREE_SKIP)
    got = {str(f.relative_to(staging / "org/languagetool")) for f in staging.rglob("*") if f.is_file()}
    assert got == set(kept)
    assert extras.EXTRAS_BY_ID["languagetool"].downloads[0].tree_skip == languagetool_files.TREE_SKIP
    assert "~200 MB on disk" in extras.EXTRAS_BY_ID["languagetool"].size


def test_overlapping_matches_are_one_underline_and_the_cold_start_wait_is_shown_then_cleared():
    """L-documents-111: measured in the page, a cold Java start held every grammar
    underline for 12.3 s (request at 3.4 s, answer at 15.6 s) with nothing said."""
    script = r"""
    const el = {textContent: "", classList: {contains: () => false}}; const seen = [];
    global.window = {docSpell: {}}; global.docSpellingVariant = () => "us"; global.$ = () => el;
    global.apiJson = async () => { seen.push(el.textContent);
      return {available: true, matches: [{start: 0, end: 8, message: "a", suggestions: []}, {start: 5, end: 12, message: "b", suggestions: []}, {start: 20, end: 24, message: "c", suggestions: []}]}; };
    eval(require("fs").readFileSync(process.argv[1], "utf8"));
    window.docSpell.languageTool([], "x".repeat(30)).then((r) => {
      console.log(JSON.stringify({spans: r.map((l) => [l.start, l.end]), during: seen[0], after: el.textContent}));
    });
    """
    path = str(ROOT / "frontend/js/documents-languagetool.js")
    out = subprocess.run(["node", "-e", script, path], capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    assert got["spans"] == [[0, 8], [20, 24]]
    assert got["during"] == "Starting the second grammar checker, which takes a few seconds the first time."
    assert got["after"] == ""


def test_harper_findings_are_drawn_before_languagetool_answers():
    text = (ROOT / "frontend/js/documents-prose.js").read_text()
    assert "if (early && lints !== null) early(lints);" in text
    assert "docGrammarAsk(text, early).then" in text
