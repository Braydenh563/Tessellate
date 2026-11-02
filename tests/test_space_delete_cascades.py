"""Deleting a space deletes what was in it.

Asked for directly: "make sure that if a specific space is deleted too, that
all the content including notes files and images etc originating in that
specific space get deleted with it as well." The route used to *reassign*
every row to "default", so a deleted space's notes reappeared elsewhere.
"""
from __future__ import annotations

import io


def _in_space(client, space_id: str):
    return {"X-Workspace-ID": space_id}


def test_notes_files_and_uploads_go_with_their_space(client):
    created = client.post("/spaces", json={"name": "Doomed"})
    assert created.status_code in (200, 201), created.text
    space_id = created.json()["id"]
    h = _in_space(client, space_id)

    note = client.post("/entries", json={"content": "only in doomed"}, headers=h).json()
    attach = client.post(
        f"/entries/{note['id']}/files",
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=h,
    )
    assert attach.status_code == 201, attach.text
    upload = client.post(
        "/media/upload",
        files={"file": ("p.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")},
        headers=h,
    )
    assert upload.status_code == 200, upload.text
    keep = client.post("/entries", json={"content": "stays in default"}).json()

    deleted = client.delete(f"/spaces/{space_id}?purge=1")
    assert deleted.status_code == 200

    everything = client.get("/entries", headers={"X-Workspace-ID": "all"}).json()
    ids = {e["id"] for e in (everything if isinstance(everything, list) else everything.get("items", []))}
    assert note["id"] not in ids, "the doomed space's note survived its space"
    assert keep["id"] in ids, "a note in another space must be untouched"
    media = client.get("/media", headers={"X-Workspace-ID": "all"}).json()
    assert all(m["original_name"] != "p.png" for m in media)
