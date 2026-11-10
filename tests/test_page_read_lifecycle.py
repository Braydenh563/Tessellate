"""A deleted file takes its stored page readings with it, and Undo brings them back.

SQLite reuses the freed highest id (no AUTOINCREMENT), so a `PageRead` row left
behind by a deleted upload showed up as the OCR text and boxes of the next file
to land on that id, and `core/readings.py` indexed it under the new file.
"""

from __future__ import annotations

import io

from tessellate.api import routes_files
from tessellate.core.database import PageRead

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def _upload(client, data: bytes = PNG) -> dict:
    res = client.post("/media/upload", files={"file": ("scan.png", io.BytesIO(data), "image/png")}, data={"direct": "true"})
    assert res.status_code in (200, 201), res.text
    return res.json()


def _read(kind: str, source_id: int, text: str) -> None:
    key = (kind, source_id)
    routes_files._remember_page_read(key, routes_files.OcrPageReadOut(page=0, text=text, model="stub"), "vision")


def _count(session, kind: str, source_id: int) -> int:
    session.expire_all()
    return session.query(PageRead).filter_by(kind=kind, source_id=source_id).count()


def test_deleting_an_upload_drops_its_page_readings(client, session):
    up = _upload(client)
    _read("upload", up["id"], "OLDFILE words")
    assert _count(session, "upload", up["id"]) == 1
    gone = client.delete(f"/media/{up['id']}")
    assert gone.status_code == 200
    assert _count(session, "upload", up["id"]) == 0


def test_undo_of_an_upload_delete_brings_its_readings_back(client, session):
    up = _upload(client)
    _read("upload", up["id"], "KEPT words")
    token = client.delete(f"/media/{up['id']}").json()["undo_token"]
    back = client.post("/media/restore", json={"token": token})
    assert back.status_code == 200, back.text
    pages = client.get(f"/media/{back.json()['id']}/page-reads").json()["pages"]
    assert [p["text"] for p in pages] == ["KEPT words"]


def test_deleting_an_attachment_drops_its_page_readings_and_undo_restores_them(client, session):
    note = client.post("/entries", json={"content": "host"}).json()
    made = client.post(f"/entries/{note['id']}/files", files={"file": ("a.txt", b"x", "text/plain")})
    aid = made.json()["attachments"][0]["id"]
    _read("attachment", aid, "ATTACHED words")
    gone = client.delete(f"/files/{aid}")
    assert gone.status_code == 200, gone.text
    assert _count(session, "attachment", aid) == 0
    back = client.post("/files/restore", json={"token": gone.json()["undo_token"]})
    assert back.status_code == 200
    assert _count(session, "attachment", aid) == 1


def test_a_new_upload_on_a_reused_id_does_not_inherit_the_old_files_reading(client, session):
    up = _upload(client)
    _read("upload", up["id"], "OLDFILE words")
    client.delete(f"/media/{up['id']}")
    fresh = _upload(client, PNG + b"\x00")
    assert fresh["id"] == up["id"]
    assert client.get(f"/media/{fresh['id']}/page-reads").json()["pages"] == []
