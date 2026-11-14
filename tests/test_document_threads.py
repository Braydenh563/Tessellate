"""Document comment threads (audit 1102 DX24, audit 1028 D26): the sidecar.

A remark stays the inline `%%remark%%`; its thread (author, time, replies,
resolved) is kept beside the text in `documents.threads` and never in the file,
so an export carries the remark as a footnote and nothing else.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core import docthreads
from tests._app_js import documents_text

COMMENTS_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-comments.js"

THREAD = {
    "id": "t1",
    "key": "1a2b3c4d.0",
    "author": "Sam",
    "at": "2026-11-02T09:00:00+00:00",
    "text": "Check this word",
    "replies": [{"author": "Sam", "at": "2026-11-02T09:05:00+00:00", "text": "Done"}],
    "resolved": True,
    "resolved_at": "2026-11-02T09:06:00+00:00",
    "target": "word",
    "line": 3,
    "own": False,
}


def test_clean_keeps_the_known_shape_and_drops_the_rest():
    out = docthreads.clean([{**THREAD, "evil": "x" * 10}])
    assert out == [THREAD]


def test_clean_survives_junk_without_raising():
    assert docthreads.clean(None) == []
    assert docthreads.clean("not a list") == []
    assert docthreads.clean([1, "a", None, {"id": ""}]) == []


def test_clean_caps_the_sizes():
    long = {**THREAD, "text": "x" * 5000, "replies": [{"author": "a", "at": "", "text": "y" * 5000}] * 500}
    out = docthreads.clean([long] * 1000)
    assert len(out) == docthreads.MAX_THREADS
    assert len(out[0]["text"]) == docthreads.MAX_TEXT
    assert len(out[0]["replies"]) == docthreads.MAX_REPLIES


def test_the_per_item_caps_do_not_bound_the_total_so_the_total_has_its_own():
    fat = {**THREAD, "text": "x" * docthreads.MAX_TEXT, "replies": [{"author": "a", "at": "", "text": "y" * docthreads.MAX_TEXT}] * docthreads.MAX_REPLIES}
    assert len(docthreads.dump([fat] * docthreads.MAX_THREADS)) > docthreads.MAX_TOTAL, "the per-item caps alone allow about 200 MB"
    assert docthreads.too_large([fat] * docthreads.MAX_THREADS)
    assert not docthreads.too_large([THREAD])
    assert not docthreads.too_large(None)


def test_a_list_over_the_total_cap_is_refused_with_a_clear_422(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    reply = {"author": "a", "at": "", "text": "y" * docthreads.MAX_TEXT}
    fat = {**THREAD, "replies": [reply] * docthreads.MAX_REPLIES}
    refused = client.put(f"/documents/{doc['id']}", json={"threads": [{**fat, "id": f"t{n}"} for n in range(10)]})
    assert refused.status_code == 422
    assert "too many comments" in refused.json()["detail"].lower()
    assert client.get(f"/documents/{doc['id']}").json()["threads"] == [THREAD], "a refused save writes nothing"


def test_a_fresh_database_lets_an_older_build_insert_a_document_without_threads(tmp_path):
    import sqlite3

    from tessellate.core.database_manager import DatabaseManager

    path = tmp_path / "fresh.db"
    DatabaseManager(path).engine.dispose()
    conn = sqlite3.connect(str(path))
    try:
        # What a build from before the column inserts: no `threads` in the list.
        conn.execute("INSERT INTO documents (title, content, file_type, created_at, updated_at) VALUES ('Old', 'x', 'md', '2026-11-01', '2026-11-01')")
        assert conn.execute("SELECT threads FROM documents").fetchone()[0] == ""
    finally:
        conn.close()


def test_dump_and_load_round_trip_and_an_old_row_loads_empty():
    assert docthreads.load(docthreads.dump([THREAD])) == [THREAD]
    assert docthreads.load("") == []
    assert docthreads.load(None) == []
    assert docthreads.load("{broken") == []


def test_a_document_without_threads_reads_as_an_empty_list(client):
    doc = client.post("/documents", json={"title": "T", "content": "a %%b%% c"}).json()
    assert client.get(f"/documents/{doc['id']}").json()["threads"] == []


def test_threads_survive_a_reload_and_an_autosave_that_omits_them(client):
    doc = client.post("/documents", json={"title": "T", "content": "a %%b%% c"}).json()
    saved = client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]}).json()
    assert saved["threads"] == [THREAD]
    again = client.put(f"/documents/{doc['id']}", json={"content": "a %%b%% c d"}).json()
    assert again["threads"] == [THREAD], "a content-only save leaves the sidecar alone"
    assert client.get(f"/documents/{doc['id']}").json()["threads"] == [THREAD]


def test_an_empty_list_clears_the_sidecar(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    cleared = client.put(f"/documents/{doc['id']}", json={"threads": []}).json()
    assert cleared["threads"] == []


def test_the_export_does_not_carry_the_sidecar(client):
    doc = client.post("/documents", json={"title": "T", "content": "See ==it== %%Check this word%%"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    exported = client.get(f"/documents/{doc['id']}/export.md").text
    assert "Sam" not in exported and "Done" not in exported


def _other(thread_id: str) -> dict:
    return {**THREAD, "id": thread_id, "key": f"k.{thread_id}", "resolved": False, "replies": []}


def test_a_read_carries_the_hash_of_the_threads(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    empty = doc["threads_hash"]
    saved = client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]}).json()
    assert saved["threads_hash"] != empty
    assert client.get(f"/documents/{doc['id']}").json()["threads_hash"] == saved["threads_hash"]


def test_two_windows_do_not_overwrite_each_others_threads(client):
    doc = client.post("/documents", json={"title": "T", "content": "a"}).json()
    base = doc["threads_hash"]
    # window A saves a thread first
    a = client.put(f"/documents/{doc['id']}", json={"threads": [THREAD], "base_threads_hash": base})
    assert a.status_code == 200
    # window B, still on the empty list, saves its own: refused, with what A saved
    b = client.put(f"/documents/{doc['id']}", json={"threads": [_other("t2")], "base_threads_hash": base})
    assert b.status_code == 409
    detail = b.json()["detail"]
    assert detail["code"] == "edit_conflict"
    assert detail["current"]["threads"] == [THREAD]
    assert client.get(f"/documents/{doc['id']}").json()["threads"] == [THREAD]


def test_a_save_that_started_from_the_current_threads_goes_through(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    first = {"threads": [THREAD], "base_threads_hash": doc["threads_hash"]}
    a = client.put(f"/documents/{doc['id']}", json=first).json()
    second = {"threads": [THREAD, _other("t2")], "base_threads_hash": a["threads_hash"]}
    b = client.put(f"/documents/{doc['id']}", json=second)
    assert b.status_code == 200 and len(b.json()["threads"]) == 2


def test_a_stale_threads_hash_with_the_same_list_is_not_a_conflict(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    body = {"threads": [THREAD], "base_threads_hash": doc["threads_hash"]}
    answer = client.put(f"/documents/{doc['id']}", json=body)
    assert answer.status_code == 200


def test_a_text_only_save_ignores_a_stale_threads_hash(client):
    doc = client.post("/documents", json={"title": "T", "content": "a"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    body = {"content": "ab", "base_hash": doc["content_hash"], "base_threads_hash": doc["threads_hash"]}
    ok = client.put(f"/documents/{doc['id']}", json=body)
    assert ok.status_code == 200, "no threads sent: nothing of the other window's would be replaced"
    assert ok.json()["threads"] == [THREAD]


def test_a_save_without_a_threads_hash_is_unchecked(client):
    doc = client.post("/documents", json={"title": "T"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    answer = client.put(f"/documents/{doc['id']}", json={"threads": [_other("t2")]})
    assert answer.status_code == 200


# --- the browser's side of it (wiring; the model itself is in test_document_thread_model.py) ---


def _function_body(text: str, header: str) -> str:
    start = text.index(header)
    return text[start : start + 6000]


def test_a_save_sends_the_panels_threads_and_the_hash_it_started_from():
    save = _function_body(documents_text(), "async function docSaveOnce(")
    assert "threads: renderDocComments.threads()" in save
    assert "base_threads_hash: currentDoc.threads_hash" in save


def test_keep_mine_adopts_their_threads_hash_and_take_theirs_reloads_the_panel():
    resolve = _function_body(documents_text(), "async function docResolveConflict(")
    assert "threads_hash: current.threads_hash" in resolve
    theirs = resolve[resolve.index('answer === "theirs"') :]
    assert "renderDocComments.reload()" in theirs
    assert theirs.index("renderDocComments.reload()") < theirs.index("docSurface().text")


def test_the_panel_reads_the_threads_off_the_document_when_it_opens():
    sync = _function_body(documents_text(), "function docThreadsSync(")
    assert "docThreads = Array.isArray(currentDoc.threads) ? currentDoc.threads : [];" in sync
    assert "docThreadsDoc = currentDoc.id" in sync


def test_nothing_is_sent_until_the_panel_has_read_the_document():
    text = documents_text()
    assert "return currentDoc && docThreadsDoc === currentDoc.id ? docThreads : undefined;" in text, (
        "undefined drops out of the JSON, so a save before the first read cannot wipe the sidecar"
    )


SYNC_DRIVER = r"""
let currentDoc = { id: 1, threads: [] };
let docThreads = [], docThreadsDoc = null, docThreadMap = {}, docCommentReplying = null;
const dirtied = [];
function markDocDirty() { dirtied.push(1); }
function docThreadAuthor() { return "Sam"; }
const comments = (text) => docCommentsParse(text);
%SYNC%
docThreadsSync(comments("a ==b== %%one%% c"));
const afterOpen = dirtied.length;
docThreadsSync(comments("a ==b== %%one%% c"));
const afterQuiet = dirtied.length;
docThreadsSync(comments("a ==b== %%one%% c %%two%%"));
const afterNew = dirtied.length;
docThreadsSync(comments("a ==b== %%one%% c %%two%%"));
const afterSettled = dirtied.length;
docThreadsSync(comments("a ==b== c"));
const afterDropped = dirtied.length;
process.stdout.write(JSON.stringify({ afterOpen, afterQuiet, afterNew, afterSettled, afterDropped, threads: docThreads.length }));
"""


def test_threads_made_or_dropped_by_the_reconcile_are_saved():
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    source = COMMENTS_JS.read_text(encoding="utf-8")
    threads_source = COMMENTS_JS.with_name("documents-threads.js").read_text(encoding="utf-8")  # moved out (L624)

    def region(begin: str, end: str) -> str:
        text = threads_source if "THREADS" in begin else source
        return text[text.index(begin) + len(begin) : text.index(end)]

    sync = source[source.index("function docThreadsSync(") :]
    sync = sync[: sync.index("\n  }\n") + 5]
    model = region("// DOC-COMMENT-BEGIN", "// DOC-COMMENT-END") + region("// DOC-THREADS-BEGIN", "// DOC-THREADS-END")
    model += "\nconst renderDocComments = { model: { docThreadsReconcile } };\n"  # the panel reaches the model through this
    out = subprocess.run(
        [node, "-e", model + SYNC_DRIVER.replace("%SYNC%", sync)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["afterOpen"] == 0, "opening a document is not an edit"
    assert got["afterQuiet"] == 0
    assert got["afterNew"] == 1, "a remark that appeared with no save of its own is a change to save"
    assert got["afterSettled"] == 1
    assert got["afterDropped"] == 2, "a thread whose remark is gone is a change to save"


def test_a_save_without_threads_keeps_them_and_one_with_junk_items_is_refused(client):
    doc = client.post("/documents", json={"title": "T", "content": "a"}).json()
    client.put(f"/documents/{doc['id']}", json={"threads": [THREAD]})
    left_out = client.put(f"/documents/{doc['id']}", json={"content": "ab", "base_hash": doc["content_hash"]})
    assert left_out.json()["threads"] == [THREAD], "the no-wipe case: a body without the key leaves the list"
    for junk in (["text"], [1], [None], "nope", {"id": "x"}):
        refused = client.put(f"/documents/{doc['id']}", json={"threads": junk})
        assert refused.status_code == 422
    assert client.get(f"/documents/{doc['id']}").json()["threads"] == [THREAD]
