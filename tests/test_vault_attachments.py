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
    made_private = client.post(f"/entries/{entry['id']}/privacy", json={"private": True})
    assert made_private.status_code == 200
    vault.close()
    return attachment_id


def test_a_locked_private_notes_files_are_refused(client, sealed_attachment):
    aid = sealed_attachment
    download = client.get(f"/files/{aid}")
    text = client.get(f"/files/{aid}/text")
    overwrite = client.put(f"/files/{aid}/text", json={"text": "overwritten"})
    assert (download.status_code, text.status_code, overwrite.status_code) == (409, 409, 409)


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
    reply = client.get(f"/files/{sealed_attachment}")
    assert reply.status_code == 200
    vault.close()


PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _sealed_image(client, session, *, also_plain=False):
    """A picture embedded in a private note (and optionally a readable one), vault locked."""
    from tessellate.core import vault
    from tessellate.core.database import MediaUpload

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    up = client.post("/media/upload", files={"file": ("p.png", PNG, "image/png")})
    assert up.status_code in (200, 201), up.text
    url = up.json()["url"]
    row = session.query(MediaUpload).filter_by(filename=url.rsplit("/", 1)[-1]).one()
    row.ocr_text = "IMGSECRET"
    session.commit()
    note = client.post("/entries", json={"content": f"private pic ![]({url})"}).json()
    made_private = client.post(f"/entries/{note['id']}/privacy", json={"private": True})
    assert made_private.status_code == 200
    if also_plain:
        plain = client.post("/entries", json={"content": f"plain pic ![]({url})"})
        assert plain.status_code == 201
    vault.close()
    return url


def test_a_locked_private_notes_picture_is_not_served(client, session):
    url = _sealed_image(client, session)
    reply = client.get(url)
    # Q18 (owner): a locked read answers 409 "Unlock first." like the link and read routes; it was 403.
    assert reply.status_code == 409
    assert reply.json()["detail"] == "Unlock first."


def test_a_picture_a_readable_note_also_uses_stays_served(client, session):
    url = _sealed_image(client, session, also_plain=True)
    reply = client.get(url)
    assert reply.status_code == 200


def test_the_picture_comes_back_once_unlocked(client, session):
    from tessellate.core import vault

    url = _sealed_image(client, session)
    vault.open_with(session, PASSPHRASE)
    reply = client.get(url)
    assert reply.status_code == 200
    vault.close()


def test_the_media_list_blanks_only_pictures_of_sealed_notes(client, session):
    from tessellate.core.database import MediaUpload

    url = _sealed_image(client, session)
    session.add(MediaUpload(filename="orphan1.png", original_name="o.png", ocr_text="ORPHANTEXT"))
    session.commit()
    text = str(client.get("/media").json())
    assert "IMGSECRET" not in text
    assert "ORPHANTEXT" in text
    assert url


def test_a_private_note_restored_to_a_version_with_a_picture_keeps_it_sealed(client, session):
    # The restore paths write a private note's text without the edit path's
    # flag (the SEC-A2 second pass's residual gap 2): a picture only an older
    # version embedded came back served to a locked session.
    from tessellate.core import vault
    from tessellate.core.database import EntryRevision
    from tessellate.entry import manager_text

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    url = client.post("/media/upload", files={"file": ("r.png", PNG, "image/png")}).json()["url"]
    note = client.post("/entries", json={"content": f"old pic ![]({url})"}).json()
    edited = client.put(f"/entries/{note['id']}", json={"content": "no picture now"})
    assert edited.status_code == 200
    made_private = client.post(f"/entries/{note['id']}/privacy", json={"private": True})
    assert made_private.status_code == 200
    revision = next(r for r in session.query(EntryRevision).filter_by(entry_id=note["id"]) if "old pic" in manager_text.readable_content(r))
    restored = client.post(f"/entries/{note['id']}/history/{revision.id}/restore")
    assert restored.status_code == 200, restored.text
    vault.close()
    reply = client.get(url)
    assert reply.status_code == 409


_PIC_ROUTES = [
    ("get", "/media/{id}/ocr-regions?auto=true", {}),
    ("post", "/media/{id}/caption", {}),
    ("post", "/media/{id}/ocr", {}),
    ("post", "/media/{id}/ocr-range-read", {}),
    ("post", "/media/{id}/ocr-page-read", {}),
    ("post", "/media/{id}/region-read", {"files": {"crop": ("c.png", PNG, "image/png")}}),
    ("post", "/media/{id}/page-caption", {}),
    ("get", "/media/{id}/page-reads", {}),
    ("delete", "/media/{id}/page-reads/0", {}),
    ("delete", "/media/{id}/readings/ocr", {}),
    ("post", "/media/{id}/ocr-clean-loops", {}),
    ("post", "/media/{id}/vision-ocr", {}),
]


@pytest.mark.parametrize(("verb", "path", "kw"), _PIC_ROUTES)
def test_a_locked_private_notes_picture_readings_are_refused(client, session, verb, path, kw):
    from tessellate.core.database import MediaUpload

    url = _sealed_image(client, session)
    uid = session.query(MediaUpload).filter_by(filename=url.rsplit("/", 1)[-1]).one().id
    reply = getattr(client, verb)(path.format(id=uid), **kw)
    assert reply.status_code == 409, reply.text
    assert "IMGSECRET" not in reply.text


def test_media_meta_is_refused_for_a_sealed_picture(client, session):
    url = _sealed_image(client, session)
    assert client.get(f"/media/meta/{url.rsplit('/', 1)[-1]}").status_code == 409


def test_media_meta_stays_open_for_a_picture_a_readable_note_shares(client, session):
    shared = _sealed_image(client, session, also_plain=True)
    assert client.get(f"/media/meta/{shared.rsplit('/', 1)[-1]}").status_code == 200
