"""The other note writers send `base_hash` too (WORLD_CLASS_PLAN 22.1 item 5, LEDGER L-world-class-98).

The note form and the document editor were checked first; this covers the
writers that edit from a copy they read earlier: an attached file's text in
the lightbox, a tag edit from the graph's stale node, and the card's
"Remove image" which rewrites the whole text. A card's task boxes are
disabled (the note's own page ticks them, through the document editor, which
already sends `base_hash`), so they have no write to check.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tests.test_file_editing import _attach


def test_a_file_read_carries_the_hash_of_its_text(client):
    attachment_id = _attach(client, "notes.md", b"# One\n")
    read = client.get(f"/files/{attachment_id}/text").json()
    assert read["content_hash"]
    client.put(f"/files/{attachment_id}/text", json={"text": "# Two\n"})
    assert client.get(f"/files/{attachment_id}/text").json()["content_hash"] != read["content_hash"]


def test_a_stale_file_save_is_refused_with_the_text_that_is_there(client):
    attachment_id = _attach(client, "notes.md", b"# One\n")
    base = client.get(f"/files/{attachment_id}/text").json()["content_hash"]
    ok = client.put(f"/files/{attachment_id}/text", json={"text": "# Theirs\n", "base_hash": base})
    assert ok.status_code == 200
    mine = client.put(f"/files/{attachment_id}/text", json={"text": "# Mine\n", "base_hash": base})
    assert mine.status_code == 409
    detail = mine.json()["detail"]
    assert detail["code"] == "edit_conflict"
    assert detail["current"]["content"] == "# Theirs\n"
    assert client.get(f"/files/{attachment_id}/text").json()["text"] == "# Theirs\n"
    kept = client.put(
        f"/files/{attachment_id}/text",
        json={"text": "# Mine\n", "base_hash": detail["current"]["content_hash"]},
    )
    assert kept.status_code == 200


def test_a_file_save_without_a_base_is_unchecked(client):
    attachment_id = _attach(client, "notes.md", b"# One\n")
    saved = client.put(f"/files/{attachment_id}/text", json={"text": "# Two\n"})
    assert saved.status_code == 200


def test_a_stale_tag_edit_is_refused_with_the_note_as_it_is(client):
    note = client.post("/entries", json={"content": "Tagged note", "tags": ["a"]}).json()
    client.put(f"/entries/{note['id']}", json={"tags": ["a", "b"]})
    stale = client.put(f"/entries/{note['id']}", json={"tags": ["a", "c"], "base_tags": ["a"]})
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "edit_conflict"
    assert sorted(detail["current"]["tags"]) == ["a", "b"]
    assert sorted(client.get(f"/entries/{note['id']}").json()["tags"]) == ["a", "b"]


def test_a_tag_edit_from_the_current_tags_goes_through(client):
    note = client.post("/entries", json={"content": "Tagged note", "tags": ["a"]}).json()
    saved = client.put(f"/entries/{note['id']}", json={"tags": ["a", "c"], "base_tags": ["a"]})
    assert saved.status_code == 200
    assert sorted(saved.json()["tags"]) == ["a", "c"]


def test_the_three_writers_send_their_base():
    lightbox = frontend_text("lightbox-view.js")
    lightbox = lightbox[lightbox.index("const saveFileBtn") :]
    lightbox = lightbox[: lightbox.index("saveFileBtn.classList.add")]
    assert "base_hash" in lightbox and "isEditConflict" in lightbox
    js = frontend_text("graph-canvas.js")
    graph = js[js.index('on("graph-selection-tag"') :]
    graph = graph[: graph.index('on("graph-selection-link"')]
    assert "base_tags" in graph and "isEditConflict" in graph
    js = frontend_text("entry-card.js")
    remove = js[js.index('"remove-inline-image"') :]
    remove = remove[: remove.index("if (glance)")]
    assert "base_hash: whole.content_hash" in remove and "isEditConflict" in remove
