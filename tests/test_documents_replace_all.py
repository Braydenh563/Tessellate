"""DOCUMENTS_PLAN 24 row 9 (Brief 76): replace in every document, one undo step.

`POST /documents/contents` writes many documents' text in one transaction:
the replace sends the results, its undo the originals. Driven in the app by
`scratchpad/ui-sweeps/docreplace76.js` (fifty documents, one Ctrl+Z).
"""

from __future__ import annotations

from tessellate.api.edit_conflicts import content_hash


def _make(client, title, content):
    return client.post("/documents", json={"title": title, "content": content}).json()


def test_fifty_documents_are_written_and_written_back_whole(client):
    docs = [_make(client, f"Doc {n}", f"colour {n} and colour") for n in range(50)]
    replaced = [{"id": d["id"], "content": d["content"].replace("colour", "color")} for d in docs]
    first = client.post("/documents/contents", json={"documents": replaced})
    assert first.status_code == 200 and len(first.json()["updated"]) == 50
    did = docs[7]["id"]
    seven = client.get(f"/documents/{did}").json()
    assert seven["content"] == "color 7 and color"
    history = client.get(f"/documents/{did}/revisions").json()
    assert len(history) == 1, "the version it replaced is kept"
    back = client.post("/documents/contents", json={"documents": [{"id": d["id"], "content": d["content"]} for d in docs]})
    assert len(back.json()["updated"]) == 50
    after = [client.get(f"/documents/{d['id']}").json()["content"] for d in docs]
    assert after == [d["content"] for d in docs]


def test_an_unknown_id_writes_nothing(client):
    doc = _make(client, "Kept", "same words")
    refused = client.post(
        "/documents/contents",
        json={"documents": [{"id": doc["id"], "content": "changed"}, {"id": 999999, "content": "x"}]},
    )
    assert refused.status_code == 404
    kept = client.get(f"/documents/{doc['id']}").json()
    assert kept["content"] == "same words"


def test_an_unchanged_document_is_not_history(client):
    doc = _make(client, "Same", "unchanged")
    same = client.post("/documents/contents", json={"documents": [{"id": doc["id"], "content": "unchanged"}]})
    assert same.json()["updated"] == []
    twice = client.post("/documents/contents", json={"documents": [{"id": doc["id"], "content": "a"}, {"id": doc["id"], "content": "b"}]})
    assert twice.status_code == 422


def test_the_dialog_replaces_through_one_request_and_one_undo_step():
    from tests._app_js import INDEX_HTML, JS_DIR

    js = (JS_DIR / "documents.js").read_text(encoding="utf-8")
    start = js.index("async function runDocReplace(")
    body = js[start: js.index("\n}\n", start)]
    assert "offerUndo(" in body and "docWriteContents(before, hashes)" in body
    assert '"/documents/contents"' in js
    assert 'id: "replace-documents"' in js and "openDocReplace()" in js
    html = INDEX_HTML.read_text(encoding="utf-8")
    for control in ("doc-replace-find", "doc-replace-with", "doc-replace-regex", "doc-replace-case", "doc-replace-run"):
        assert f'id="{control}"' in html, control


def test_every_documents_text_is_read_in_one_request(client):
    """OPEN row 1055: the scan read `/documents` (one page) and then each
    document by its own request, so past the first page it missed documents
    and at fifty it cost fifty-one requests."""
    docs = [_make(client, f"Doc {n}", f"text {n}") for n in range(3)]
    archived = _make(client, "Shelved", "text shelved")
    client.put(f"/documents/{archived['id']}/archive")
    got = client.get("/documents/contents")
    assert got.status_code == 200
    rows = {row["id"]: row for row in got.json()}
    assert set(rows) == {d["id"] for d in docs}
    assert rows[docs[1]["id"]] == {"id": docs[1]["id"], "title": "Doc 1", "file_type": "md", "content": "text 1", "content_hash": content_hash("text 1")}


def test_the_scan_is_one_request_and_the_dock_menu_has_the_row():
    from tests._app_js import INDEX_HTML, JS_DIR

    js = (JS_DIR / "documents.js").read_text(encoding="utf-8")
    start = js.index("async function docReplaceScan(")
    body = js[start: js.index("\n}\n", start)]
    assert 'apiJson("/documents/contents")' in body and "/documents/${" not in body
    html = INDEX_HTML.read_text(encoding="utf-8")
    menu = html[html.index('id="doc-dock-menu"'): html.index("</details>", html.index('id="doc-dock-menu"'))]
    assert 'id="doc-replace-everywhere"' in menu
    assert '$("doc-replace-everywhere")' in js


def test_an_undo_over_a_later_edit_writes_nothing(client):
    """Audit 1028 D11: the undo wrote the old text back with no hash check,
    wiping any edit made to one of those documents since. Each item carries
    the hash of the text it was worked out from; one stale item refuses the
    whole batch, the way the batch lands whole."""
    a, b = _make(client, "A", "colour a"), _make(client, "B", "colour b")
    scan = {row["id"]: row for row in client.get("/documents/contents").json()}
    replaced = [{"id": d["id"], "content": d["content"].replace("colour", "color"), "base_hash": scan[d["id"]]["content_hash"]} for d in (a, b)]
    hashes = client.post("/documents/contents", json={"documents": replaced}).json()["hashes"]
    edited = client.get(f"/documents/{b['id']}").json()
    client.put(f"/documents/{b['id']}", json={"content": "color b, and a later line", "base_hash": edited["content_hash"]})
    undo = [{"id": d["id"], "content": d["content"], "base_hash": hashes[str(d["id"])]} for d in (a, b)]
    refused = client.post("/documents/contents", json={"documents": undo})
    assert refused.status_code == 409, refused.text
    assert "1 of these documents changed" in refused.json()["detail"]
    assert client.get(f"/documents/{a['id']}").json()["content"] == "color a"
    assert client.get(f"/documents/{b['id']}").json()["content"] == "color b, and a later line"
    #: The hashes the write returned are what the undo needs when nothing moved.
    fresh = {row["id"]: row["content_hash"] for row in client.get("/documents/contents").json()}
    assert fresh[a["id"]] == hashes[str(a["id"])]


def test_an_archived_document_is_not_written_and_media_is_processed(client, monkeypatch):
    """Audit 1028 D13: the batch write skipped the committed-media hook a
    save runs, and wrote into an archived document."""
    from tessellate.api import routes_documents

    seen = []
    monkeypatch.setattr(routes_documents, "_process_committed_media", lambda _s, content: seen.append(content))
    shelved = _make(client, "Shelved", "old words")
    client.put(f"/documents/{shelved['id']}/archive")
    refused = client.post("/documents/contents", json={"documents": [{"id": shelved["id"], "content": "new words"}]})
    assert refused.status_code == 409
    assert client.get(f"/documents/{shelved['id']}").json()["content"] == "old words"
    live = _make(client, "Live", "no picture")
    seen.clear()  # creating a document runs the hook too
    client.post("/documents/contents", json={"documents": [{"id": live["id"], "content": "![](/media/a.png)"}]})
    assert seen == ["![](/media/a.png)"]
