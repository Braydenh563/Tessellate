"""SEC-A2: a locked private note's attachments are as sealed as its words."""

from __future__ import annotations

import io
import zipfile

import pytest

PASSPHRASE = "test-passphrase"
SECRET = "ATTACHSECRET budget numbers 4242"


@pytest.fixture()
def sealed_attachment(client, session):
    from tessellate.core import vault

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    entry = client.post("/entries", json={"content": "plain body"}).json()
    made = client.post(f"/entries/{entry['id']}/files", files={"file": ("s.txt", SECRET.encode(), "text/plain")})
    assert made.status_code == 201, made.text
    attachment_id = made.json()["attachments"][0]["id"]
    assert client.post(f"/entries/{entry['id']}/privacy", json={"private": True}).status_code == 200
    vault.close()
    return attachment_id


def test_a_locked_private_notes_files_are_refused(client, sealed_attachment):
    aid = sealed_attachment
    assert client.get(f"/files/{aid}").status_code == 409
    assert client.get(f"/files/{aid}/text").status_code == 409
    assert client.put(f"/files/{aid}/text", json={"text": "overwritten"}).status_code == 409


def test_the_folder_export_leaves_out_a_locked_private_notes_files(client, sealed_attachment):
    reply = client.get("/export/folder")
    assert reply.status_code == 200, reply.text
    with zipfile.ZipFile(io.BytesIO(reply.content)) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
        names = " ".join(zf.namelist())
    assert SECRET.encode() not in blob
    assert "s.txt" not in names


def test_search_does_not_name_a_locked_private_notes_file(client, sealed_attachment):
    assert client.get("/search", params={"q": "s.txt"}).json()["hits"] == []


def test_files_come_back_once_unlocked(client, session, sealed_attachment):
    from tessellate.core import vault

    vault.open_with(session, PASSPHRASE)
    assert client.get(f"/files/{sealed_attachment}").status_code == 200
    vault.close()


def test_the_media_list_hides_the_text_of_uploads_it_cannot_place_while_locked(client, session, sealed_attachment):
    from tessellate.core.database import MediaUpload

    session.add(MediaUpload(filename="abc123.png", original_name="x.png", ocr_text="MEDIASECRET", caption="MEDIACAP"))
    session.commit()
    rows = client.get("/media").json()
    assert rows and "MEDIASECRET" not in str(rows) and "MEDIACAP" not in str(rows)
