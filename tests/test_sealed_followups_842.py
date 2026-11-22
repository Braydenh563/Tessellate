"""L-world-class-842, 843, 844: follow-ups of the L670 sealed writers.

A shut door writes nothing plain and says so (SECURITY.md T10, T23, T28).
"""

from __future__ import annotations

import pytest

from tessellate.core import deps, sealed_files
from tessellate.core.database import Document, Entry, impersonate_workspace
from tests import test_sealed_writes_670 as _w670
from tests.test_captions import CHUNK
from tests.test_sealed_writes_670 import _recording_files, _speech, _spools

# The L670 fixtures, bound by assignment so pytest finds them here; an import would read as unused.
helper = _w670.helper
signed_in = _w670.signed_in


def _entry(entry_id: int) -> Entry:
    session = deps.get_db().session()
    try:
        with impersonate_workspace(session, ""):
            row = session.get(Entry, entry_id)
            session.expunge(row)
            return row
    finally:
        session.close()


def _document(document_id: int) -> Document:
    session = deps.get_db().session()
    try:
        with impersonate_workspace(session, ""):
            row = session.get(Document, document_id)
            session.expunge(row)
            return row
    finally:
        session.close()


# --- 842 ------------------------------------------------------------------------------


def test_a_note_of_a_deleted_private_space_is_no_longer_sealed_by_a_space(signed_in):
    client = signed_in
    note = client.post("/entries", json={"content": "host"}, headers=client.space).json()["id"]
    assert _entry(note).sealed_by_space is True
    gone = client.delete(f"/spaces/{client.space_id}?move_to=default")
    assert gone.status_code == 200, gone.text
    moved = _entry(note)
    assert moved.workspace_id == "default"
    assert moved.sealed_by_space is False  # no space is left to have sealed it
    assert moved.is_private  # still its own private note, content unchanged


def test_undo_of_that_delete_makes_the_note_sealed_by_its_space_again(signed_in):
    client = signed_in
    note = client.post("/entries", json={"content": "host"}, headers=client.space).json()["id"]
    gone = client.delete(f"/spaces/{client.space_id}?move_to=default")
    back = client.post("/spaces/restore", json=gone.json()["restore"])
    assert back.status_code == 200, back.text
    assert _entry(note).sealed_by_space is True


def test_a_document_of_a_deleted_private_space_is_no_longer_sealed_by_a_space(signed_in):
    """The same for a document (L-world-class-892): one still marked sealed by
    a space that is gone would be unsealed by a later move in and out."""
    client = signed_in
    doc = client.post("/documents", json={"title": "Plan", "content": "boathouse"}, headers=client.space).json()["id"]
    assert _document(doc).sealed_by_space is True
    gone = client.delete(f"/spaces/{client.space_id}?move_to=default")
    assert gone.status_code == 200, gone.text
    moved = _document(doc)
    assert moved.workspace_id == "default"
    assert moved.sealed_by_space is False
    assert moved.is_private  # still sealed, now its own


def test_undo_of_that_delete_makes_the_document_sealed_by_its_space_again(signed_in):
    client = signed_in
    doc = client.post("/documents", json={"title": "Plan", "content": "boathouse"}, headers=client.space).json()["id"]
    gone = client.delete(f"/spaces/{client.space_id}?move_to=default")
    back = client.post("/spaces/restore", json=gone.json()["restore"])
    assert back.status_code == 200, back.text
    assert _document(doc).sealed_by_space is True


# --- 843 ------------------------------------------------------------------------------


def test_a_kept_wav_is_never_left_plain_when_the_space_key_is_missing(signed_in, helper):
    from tessellate.api import routes_captions

    client = signed_in
    pcm = _speech()
    sid = client.post(
        "/voice/captions/start", json={"keep_audio": True}, headers=client.space
    ).json()["id"]
    for i in range(0, len(pcm), CHUNK):
        sent = client.post(f"/voice/captions/{sid}/audio", content=pcm[i : i + CHUNK], headers=client.space)
        assert sent.status_code == 200
    before = _recording_files()
    client.post("/private-spaces/lock")  # the key goes before Stop
    done = client.post(f"/voice/captions/{sid}/stop", headers=client.space)
    assert done.status_code in (200, 423), done.text
    leaked = [p for p in _recording_files() if p not in before and not sealed_files.is_sealed(p)]
    assert leaked == []
    assert routes_captions  # the module under test


def test_seal_if_private_refuses_rather_than_leave_the_file_plain(signed_in, tmp_path):
    from tessellate.api import routes_captions

    client = signed_in
    dest = tmp_path / "x.wav"
    dest.write_bytes(b"RIFF plain speech")
    client.post("/private-spaces/lock")
    session = deps.get_db().session()
    try:
        row = type("R", (), {"workspace_id": client.space_id})()
        with pytest.raises(sealed_files.SealedLocked):
            routes_captions._seal_if_private(session, row, dest)
    finally:
        session.close()
    assert dest.read_bytes() == b"RIFF plain speech"  # the caller removes it


# --- 844 ------------------------------------------------------------------------------


def test_a_shut_door_in_feed_is_a_clean_423_and_writes_nothing_plain(signed_in, helper):
    client = signed_in
    pcm = _speech()
    sid = client.post(
        "/voice/captions/start", json={"keep_audio": True}, headers=client.space
    ).json()["id"]
    sent = client.post(f"/voice/captions/{sid}/audio", content=pcm[:CHUNK], headers=client.space)
    assert sent.status_code == 200
    client.post("/private-spaces/lock")
    got = client.post(f"/voice/captions/{sid}/audio", content=pcm[CHUNK : 2 * CHUNK], headers=client.space)
    assert got.status_code == 423, got.text
    assert got.json()["detail"]
    for spool in _spools():
        assert sealed_files.is_sealed(spool)
        assert pcm[CHUNK : 2 * CHUNK] not in spool.read_bytes()


def test_a_key_lost_mid_feed_is_a_423_not_a_500(signed_in, helper, monkeypatch):
    """The door shuts between the request's check and the spool append."""
    client = signed_in
    pcm = _speech()
    sid = client.post(
        "/voice/captions/start", json={"keep_audio": True}, headers=client.space
    ).json()["id"]

    def shut(*args, **kwargs):
        raise sealed_files.SealedLocked(sealed_files.LOCKED_DETAIL)

    monkeypatch.setattr(sealed_files, "append", shut)
    got = client.post(f"/voice/captions/{sid}/audio", content=pcm[:CHUNK], headers=client.space)
    assert got.status_code == 423, got.text
    assert got.json()["detail"] == sealed_files.LOCKED_DETAIL
    assert _spools() == [] or all(sealed_files.is_sealed(s) for s in _spools())
