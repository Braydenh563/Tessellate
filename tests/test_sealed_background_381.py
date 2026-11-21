"""L-world-class-381: a private space's sealed files are read in the background.

A background run used to have no vault key, so a private space's recording
answered 409 to "transcribe in the background" and an attached document was
never read. The run now borrows the grant of the session that started it
(`vault.acting_for`, SECURITY.md T28): it reads the sealed bytes and writes
the sealed result as that session, only while that session has the private
space open, and the key is never copied or written anywhere. Stubbed
transcriber: faster-whisper is not installed here (CLAUDE.md 4).
"""

from __future__ import annotations

import threading

import pytest

from tessellate.ai import voice
from tessellate.core import deps, recordings, sealed_files, spacelock, vault

PASSWORD = "first-pass"
SECRET = b"the locker code is 4715 behind the boathouse"
WEBM = bytes.fromhex("1a45dfa3") + b"\x00" * 12
SEGMENTS = [
    {"start": 0, "end": 4000, "text": "Locker four seven."},
    {"start": 4000, "end": 9000, "text": "Behind the boathouse."},
]


@pytest.fixture()
def signed_in(client):
    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    made = client.post("/spaces", json={"name": "Vault", "is_private": True})
    assert made.status_code == 200, made.text
    got = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert got.status_code == 200, got.text
    client.space = {"X-Workspace-ID": made.json()["id"]}
    yield client
    spacelock.close_all()


def _recording(client):
    made = client.post("/recordings", json={"title": "standup", "mime": "audio/webm"}, headers=client.space)
    rid = made.json()["id"]
    got = client.post(
        f"/recordings/{rid}/chunk", files={"file": ("c", WEBM + SECRET, "audio/webm")}, data={"at": "0"}, headers=client.space
    )
    assert got.status_code == 200, got.text
    client.post(f"/recordings/{rid}/finish", json={"duration_ms": 9000}, headers=client.space)
    return rid


def _raw_segments(rid):
    from sqlalchemy import text

    with deps.get_db().engine.connect() as conn:
        return conn.execute(text("SELECT segments FROM recordings WHERE id = :i"), {"i": rid}).scalar()


def _left_in_tmp():
    root = deps.get_config().data_dir / "tmp"
    return sorted(p.name for p in root.glob(sealed_files.OPEN_PREFIX + "*")) if root.is_dir() else []


def test_a_sealed_recording_is_transcribed_in_the_background_and_kept_sealed(signed_in, monkeypatch):
    client = signed_in
    heard = []

    def fake(path, model_size="base"):
        heard.append(open(path, "rb").read())
        yield from SEGMENTS

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", fake)
    rid = _recording(client)
    started = client.post(f"/recordings/{rid}/transcribe/start", headers=client.space)
    assert started.status_code == 202, started.text
    assert recordings.wait_transcription(rid, 5)
    body = client.get(f"/recordings/{rid}", headers=client.space).json()
    assert body["transcription"]["state"] == "done", body["transcription"]
    assert heard == [WEBM + SECRET]
    lines = client.get(f"/recordings/{rid}/transcript", headers=client.space).json()["segments"]
    assert [line["text"] for line in lines] == [seg["text"] for seg in SEGMENTS]
    raw = _raw_segments(rid)
    assert raw and "boathouse" not in raw
    assert _left_in_tmp() == []


def test_locking_the_space_mid_run_stops_it_keeps_nothing_and_removes_the_copy(signed_in, monkeypatch):
    client = signed_in
    first_out, go_on = threading.Event(), threading.Event()

    def slow(path, model_size="base"):
        yield SEGMENTS[0]
        first_out.set()
        go_on.wait(5)
        yield SEGMENTS[1]

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", slow)
    rid = _recording(client)
    started = client.post(f"/recordings/{rid}/transcribe/start", headers=client.space)
    assert started.status_code == 202, started.text
    assert first_out.wait(5)
    assert len(_left_in_tmp()) == 1
    locked = client.post("/private-spaces/lock")
    assert locked.status_code == 200, locked.text
    go_on.set()
    assert recordings.wait_transcription(rid, 5)
    run = client.get(f"/recordings/{rid}").json().get("transcription") or recordings.transcription_of(rid)
    assert run["state"] == "failed"
    assert run.get("error") == sealed_files.BACKGROUND_LOCKED_DETAIL
    assert _raw_segments(rid) in (None, "", "[]")
    assert _left_in_tmp() == []


def test_a_closed_space_is_refused_before_a_run_starts(signed_in, monkeypatch):
    client = signed_in
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    rid = _recording(client)
    spacelock.close_all()
    got = client.post(f"/recordings/{rid}/transcribe/start", headers=client.space)
    assert got.status_code in (403, 404, 423), got.text


def test_the_borrowed_grant_ends_with_the_session(signed_in):
    """The job holds a token, never the key: once the session is revoked,
    `key()` inside `acting_for` answers nothing."""
    token = signed_in.headers["X-Auth-Token"]
    got = []

    def run():
        with vault.acting_for(token):
            got.append(vault.key() is not None)
            vault.revoke([token])
            got.append(vault.key() is not None)

    with vault.request_scope(token):
        assert vault.requester() == token
    worker = threading.Thread(target=run)
    worker.start()
    worker.join(5)
    assert got == [True, False]
    assert vault.requester() is None  # outside any request


def _attach_held(client, monkeypatch):
    """Attach a file in the private space with the queued read held back, so
    the test runs it on its own thread, as the worker would."""
    from tessellate.ai import docreader

    monkeypatch.setattr(docreader.jobs, "enqueue", lambda *a, **k: 0)
    note = client.post("/entries", json={"content": "host note"}, headers=client.space).json()
    made = client.post(
        f"/entries/{note['id']}/files", files={"file": ("plan.txt", SECRET, "text/plain")}, headers=client.space
    )
    assert made.status_code == 201, made.text
    return made.json()["attachments"][-1]["id"]


def _ocr_of(aid, token=None):
    from sqlalchemy import text

    from tessellate.core.database import Attachment, impersonate_workspace

    with deps.get_db().engine.connect() as conn:
        raw = conn.execute(text("SELECT ocr_text FROM attachments WHERE id = :i"), {"i": aid}).scalar()
    if token is None:
        return raw, None
    session = deps.get_db().session()
    try:
        with vault.request_scope(token), impersonate_workspace(session, ""):
            return raw, session.get(Attachment, aid).ocr_text
    finally:
        session.close()


def _off_request(fn, *args):
    out = []
    worker = threading.Thread(target=lambda: out.append(fn(*args)))
    worker.start()
    worker.join(10)
    return out


def test_a_sealed_attachment_is_read_in_the_background_and_its_text_kept_sealed(signed_in, monkeypatch):
    from tessellate.ai import docreader

    client = signed_in
    aid = _attach_held(client, monkeypatch)
    _off_request(docreader.read_document_and_store, aid)
    raw, plain = _ocr_of(aid, client.headers["X-Auth-Token"])
    assert raw and "boathouse" not in raw
    assert "boathouse" in plain


def test_a_sealed_attachment_waits_when_no_session_handed_it_over(signed_in, monkeypatch):
    """After a restart nobody started the read: it is skipped, as before,
    and read the next time a session opens it."""
    from tessellate.ai import docreader

    client = signed_in
    aid = _attach_held(client, monkeypatch)
    docreader.forget_sessions()
    _off_request(docreader.read_document_and_store, aid)
    assert _ocr_of(aid)[0] is None


def test_a_closed_space_stops_the_read(signed_in, monkeypatch):
    from tessellate.ai import docreader

    client = signed_in
    aid = _attach_held(client, monkeypatch)
    client.post("/private-spaces/lock")
    _off_request(docreader.read_document_and_store, aid)
    assert _ocr_of(aid)[0] is None
