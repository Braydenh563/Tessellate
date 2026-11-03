"""Document comment threads (audit 1102 DX24, audit 1028 D26): the sidecar.

A remark stays the inline `%%remark%%`; its thread (author, time, replies,
resolved) is kept beside the text in `documents.threads` and never in the file,
so an export carries the remark as a footnote and nothing else.
"""

from __future__ import annotations

from tessellate.core import docthreads

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
