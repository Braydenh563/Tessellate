"""L-world-class-52: a private space's file bytes are sealed at rest.

L697 sealed the database columns of a private space's recordings, library
uploads and note files; their bytes on disk were still plain. What must hold:
the bytes are ciphertext on disk, read back plain while the space is open
(an audio Range read included), refused while it is locked; a plain file
from before keeps working and is sealed at the next unlock; leaving the space
writes it back plain.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from tessellate.core import deps, sealed_files, spacelock, vault

PASSWORD = "first-pass"
SECRET = b"the locker code is 4715 behind the boathouse"
WEBM = bytes.fromhex("1a45dfa3") + b"\x00" * 12


@pytest.fixture()
def signed_in(client):
    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    yield client
    spacelock.close_all()


def _space(client, private=True):
    made = client.post("/spaces", json={"name": "Vault", "is_private": private})
    assert made.status_code == 200, made.text
    return made.json()["id"]


def _unlock(client):
    got = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert got.status_code == 200, got.text


def _h(space):
    return {"X-Workspace-ID": space}


def _png() -> bytes:
    """A one-pixel PNG with the secret in a text chunk."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    head = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    text = chunk(b"tEXt", b"Comment\x00" + SECRET)
    pixel = chunk(b"IDAT", zlib.compress(b"\x00\x00"))
    return b"\x89PNG\r\n\x1a\n" + head + text + pixel + chunk(b"IEND", b"")


def _on_disk() -> bytes:
    data_dir = deps.get_config().data_dir
    return b"".join(
        p.read_bytes() for folder in ("uploads", "media", "recordings") for p in (data_dir / folder).rglob("*") if p.is_file()
    )


def _attach(client, space, body=SECRET, name="plan.txt"):
    note = client.post("/entries", json={"content": "host note"}, headers=_h(space))
    assert note.status_code == 201, note.text
    nid = note.json()["id"]
    got = client.post(f"/entries/{nid}/files", files={"file": (name, body, "text/plain")}, headers=_h(space))
    assert got.status_code == 201, got.text
    return nid, got.json()["attachments"][-1]["id"]


def _attachment_path(aid):
    from tessellate.core.database import Attachment, impersonate_workspace

    session = deps.get_db().session()
    try:
        with impersonate_workspace(session, ""):
            row = session.get(Attachment, aid)
            return deps.get_config().uploads_dir / row.stored_name
    finally:
        session.close()


def test_the_cipher_round_trips_frames_ranges_and_appends(signed_in, tmp_path):
    """The format itself: whole reads, Range slices across frames, appends."""
    _space(signed_in)
    _unlock(signed_in)
    with vault.request_scope(signed_in.headers["X-Auth-Token"]):
        path = tmp_path / "a.bin"
        data = bytes(range(256)) * (sealed_files.FRAME // 128 + 3)
        sealed_files.append(path, data[:1000], sealed=True)
        sealed_files.append(path, data[1000:], sealed=True)
        assert sealed_files.is_sealed(path)
        assert sealed_files.read(path) == data
        assert sealed_files.plain_size(path) == len(data)
        start, end = sealed_files.FRAME - 7, sealed_files.FRAME + 9
        assert sealed_files.read_range(path, start, end) == data[start : end + 1]
        assert sealed_files.unseal(path) and path.read_bytes() == data
        assert sealed_files.seal(path) and sealed_files.read(path) == data
    vault.close()
    with pytest.raises(sealed_files.SealedLocked):
        sealed_files.read(path)


def test_a_note_file_and_a_library_upload_are_sealed_and_read_back(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _nid, aid = _attach(client, space)
    png = _png()
    up = client.post("/media/upload", files={"file": ("p.png", png, "image/png")}, data={"direct": "false"}, headers=_h(space))
    assert up.status_code == 200, up.text
    assert SECRET not in _on_disk()
    assert sealed_files.is_sealed(_attachment_path(aid))
    got = client.get(f"/files/{aid}", headers=_h(space))
    assert got.status_code == 200 and got.content == SECRET
    got = client.get(up.json()["url"], headers=_h(space))
    assert got.status_code == 200 and got.content == png
    assert got.headers["content-type"] == "image/png"


def test_a_recording_is_sealed_chunk_by_chunk_and_still_seeks(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    made = client.post("/recordings", json={"title": "standup", "mime": "audio/webm"}, headers=_h(space))
    assert made.status_code == 201, made.text
    rid = made.json()["id"]
    audio = WEBM + SECRET
    for at, part in ((0, audio[:20]), (20, audio[20:])):
        got = client.post(
            f"/recordings/{rid}/chunk", files={"file": ("c", part, "audio/webm")}, data={"at": str(at)}, headers=_h(space)
        )
        assert got.status_code == 200, got.text
    finished = client.post(f"/recordings/{rid}/finish", json={"duration_ms": 1000}, headers=_h(space))
    assert finished.status_code == 200
    assert SECRET not in _on_disk()
    whole = client.get(f"/media/recordings/{rid}", headers=_h(space))
    assert whole.status_code == 200 and whole.content == audio
    part = client.get(f"/media/recordings/{rid}", headers={**_h(space), "Range": "bytes=18-29"})
    assert part.status_code == 206 and part.content == audio[18:30]
    assert part.headers["content-range"] == f"bytes 18-29/{len(audio)}"
    tail = client.get(f"/media/recordings/{rid}", headers={**_h(space), "Range": "bytes=-5"})
    assert tail.status_code == 206 and tail.content == audio[-5:]


def test_reads_are_refused_while_the_space_is_locked(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _nid, aid = _attach(client, space)
    up = client.post("/media/upload", files={"file": ("p.png", _png(), "image/png")}, headers=_h(space)).json()
    client.post("/private-spaces/lock")
    got = client.get(f"/files/{aid}", headers=_h(space))
    assert got.status_code in (404, 409, 423) and SECRET not in got.content
    got = client.get(up["url"])
    assert got.status_code == 423 and SECRET not in got.content


def test_a_plain_file_from_before_still_reads_and_is_sealed_at_the_next_unlock(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _nid, aid = _attach(client, space)
    path = _attachment_path(aid)
    with vault.request_scope(client.headers["X-Auth-Token"]):
        sealed_files.unseal(path)  # what a file written before this change looks like
    assert path.read_bytes() == SECRET
    before = client.get(f"/files/{aid}", headers=_h(space))
    assert before.content == SECRET
    client.post("/private-spaces/lock")
    _unlock(client)
    assert sealed_files.is_sealed(path) and SECRET not in _on_disk()
    after = client.get(f"/files/{aid}", headers=_h(space))
    assert after.content == SECRET


def test_turning_a_space_private_seals_its_files_and_ordinary_unseals_them(signed_in):
    client = signed_in
    space = _space(client, private=False)
    _nid, aid = _attach(client, space)
    assert SECRET in _on_disk()
    _unlock(client)
    on = client.put(f"/spaces/{space}/private", json={"private": True})
    assert on.status_code == 200
    assert SECRET not in _on_disk()
    off = client.put(f"/spaces/{space}/private", json={"private": False, "keep_private": False})
    assert off.status_code == 200, off.text
    assert _attachment_path(aid).read_bytes() == SECRET


def test_moving_a_note_out_writes_its_file_back_plain(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    nid, aid = _attach(client, space)
    assert sealed_files.is_sealed(_attachment_path(aid))
    got = client.post("/spaces/default/move-notes", json={"ids": [nid], "keep_private": False}, headers=_h(space))
    assert got.status_code == 200, got.text
    assert _attachment_path(aid).read_bytes() == SECRET
    got = client.post(f"/spaces/{space}/move-notes", json={"ids": [nid]})
    assert got.status_code == 200, got.text
    assert sealed_files.is_sealed(_attachment_path(aid))


def test_editing_a_sealed_text_file_keeps_it_sealed(signed_in):
    client = signed_in
    space = _space(client)
    _unlock(client)
    _nid, aid = _attach(client, space, body=b"first draft", name="draft.md")
    got = client.put(f"/files/{aid}/text", json={"text": SECRET.decode()}, headers=_h(space))
    assert got.status_code == 200, got.text
    assert got.json()["text"] == SECRET.decode()
    assert SECRET not in _on_disk()
    reread = client.get(f"/files/{aid}/text", headers=_h(space))
    assert reread.json()["text"] == SECRET.decode()


def test_an_open_private_space_chosen_for_export_carries_its_files_readable(signed_in):
    """A backup copies the folders as they are (sealed, the same key opens them
    after a restore); the folder export, asked to include an open private
    space, writes its notes readable and so its files too."""
    import io
    import zipfile

    client = signed_in
    space = _space(client)
    _unlock(client)
    _attach(client, space)
    got = client.get("/export/folder", params={"include_private_spaces": "1"}, headers={"X-Workspace-ID": "all"})
    assert got.status_code == 200, got.text
    archive = zipfile.ZipFile(io.BytesIO(got.content))
    files = [archive.read(name) for name in archive.namelist() if name.endswith("plan.txt")]
    assert files == [SECRET]
    made = client.post("/backups")
    assert made.status_code in (200, 201), made.text
    blobs = b"".join(p.read_bytes() for p in (deps.get_config().data_dir / "backups").rglob("*") if p.is_file())
    assert blobs and SECRET not in blobs
