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


# The review of 43ff8e597: each test below names the finding it holds.


def _start(client, rid, path="transcribe/start"):
    started = client.post(f"/recordings/{rid}/{path}", headers=client.space)
    assert started.status_code == 202, started.text
    assert recordings.wait_transcription(rid, 5)
    return recordings.transcription_of(rid)


def _failed_closed(run, rid):
    assert run["state"] == "failed", run
    assert run.get("error") == sealed_files.BACKGROUND_LOCKED_DETAIL
    assert _raw_segments(rid) in (None, "", "[]")
    assert _left_in_tmp() == []


def _whisper(monkeypatch, segments=SEGMENTS):
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", lambda path, model_size="base": iter(segments))


def _hand_over(docreader, token, aid):
    """`read_in_background` as the upload route calls it: inside a request."""
    with vault.request_scope(token):
        docreader.read_in_background(aid)


def test_a_lock_at_the_last_step_before_the_write_keeps_nothing(signed_in, monkeypatch):
    """Finding 1: the door is looked at immediately before the commit, not
    only before the database step starts."""
    from tessellate.api import routes_recordings

    client = signed_in
    _whisper(monkeypatch)
    real = routes_recordings.log_action

    def lock_then_log(*args, **kwargs):
        spacelock.close_all()
        return real(*args, **kwargs)

    rid = _recording(client)
    monkeypatch.setattr(routes_recordings, "log_action", lock_then_log)
    _failed_closed(_start(client, rid), rid)


def test_a_private_run_is_never_named_by_the_model_nor_reads_the_meeting_note(signed_in, monkeypatch):
    """Finding 2 (SECURITY.md T28, T10): the utility model never reads a
    private transcript in the background; an ordinary space's still is."""
    from tessellate.api import routes_recordings

    client = signed_in
    named, read = [], []

    class Running:
        def is_running(self):
            return True

    _whisper(monkeypatch)
    monkeypatch.setattr(routes_recordings.deps, "get_ollama", lambda: Running())
    monkeypatch.setattr(routes_recordings.speakers, "label", lambda segs, *a, **k: named.append(len(segs)) or segs)
    monkeypatch.setattr(routes_recordings, "_people_at", lambda *a: read.append(1) or [])
    rid = _recording(client)
    assert _start(client, rid)["state"] == "done"
    assert named == [] and read == []
    ordinary = client.post("/recordings", json={"title": "open", "mime": "audio/webm"}).json()["id"]
    client.post(f"/recordings/{ordinary}/chunk", files={"file": ("c", WEBM, "audio/webm")}, data={"at": "0"})
    client.post(f"/recordings/{ordinary}/finish", json={"duration_ms": 9000})
    got = client.post(f"/recordings/{ordinary}/transcribe/start")
    assert got.status_code == 202, got.text
    assert recordings.wait_transcription(ordinary, 5)
    assert named == [2]


def test_the_watcher_removes_the_plain_copy_during_a_long_step(signed_in, monkeypatch):
    """Finding 3: a lock in the middle of one long step (a long whisper
    segment) removes the plain copy at the watcher's next look, without the
    step ending, and the run fails closed. Each look is a tick the test
    gives, never a real sleep."""
    import queue

    client = signed_in
    looked, ticks = queue.Queue(), threading.Semaphore(0)
    in_step, go_on, seen = threading.Event(), threading.Event(), []

    def tick(done, seconds):
        looked.put(seconds)
        ticks.acquire()
        return done.is_set()

    def long_segment(path, model_size="base"):
        in_step.set()
        go_on.wait(5)
        seen.append(_left_in_tmp())
        yield SEGMENTS[0]

    monkeypatch.setattr(sealed_files, "watch_wait", tick)
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", long_segment)
    rid = _recording(client)
    got = client.post(f"/recordings/{rid}/transcribe/start", headers=client.space)
    assert got.status_code == 202, got.text
    assert in_step.wait(5)
    assert looked.get(timeout=5) == sealed_files.WATCH_SECONDS
    assert len(_left_in_tmp()) == 1
    ticks.release()  # a look while the space is open: the copy stays
    looked.get(timeout=5)
    assert len(_left_in_tmp()) == 1
    spacelock.close_all()
    ticks.release()
    looked.get(timeout=5)  # the look that saw the door shut has finished
    assert _left_in_tmp() == []
    go_on.set()
    assert recordings.wait_transcription(rid, 5)
    ticks.release()  # the watcher's last wait sees the block has ended
    assert seen == [[]]
    _failed_closed(recordings.transcription_of(rid), rid)


def test_a_sealed_recording_outside_a_private_space_is_refused_up_front(signed_in, monkeypatch):
    """Finding 4: a space turned ordinary that kept its files private holds
    sealed audio; that is a 409 before any run starts, not a 202 and then a
    wrong "the private space locked" failure."""
    from sqlalchemy import text

    from tessellate.api import routes_recordings

    client = signed_in
    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    rid = _recording(client)
    with deps.get_db().engine.begin() as conn:
        conn.execute(text("UPDATE spaces SET is_private = 0 WHERE id = :s"), {"s": client.space["X-Workspace-ID"]})
    got = client.post(f"/recordings/{rid}/transcribe/start", headers=client.space)
    assert got.status_code == 409, got.text
    assert got.json()["detail"] == routes_recordings.SEALED_OUTSIDE_PRIVATE
    assert (recordings.transcription_of(rid) or {}).get("state") != "running"


def test_a_sealed_write_refused_is_the_modules_own_sentence(signed_in, monkeypatch):
    """Finding 6: the database's "cannot be written while the vault is
    locked" never reaches the run's failure line."""
    from tessellate.api import routes_recordings
    from tessellate.core.database import SealedWriteRefused

    client = signed_in
    _whisper(monkeypatch)

    def refused(*args, **kwargs):
        raise SealedWriteRefused("a private row cannot be written while the vault is locked")

    rid = _recording(client)
    monkeypatch.setattr(routes_recordings, "log_action", refused)
    _failed_closed(_start(client, rid), rid)


def _three_lines_shut_after_one(client, monkeypatch, shut):
    """A run whose space shuts (by `shut`) as the second line is heard;
    returns the lines the transcriber was asked for."""
    pulled = []

    def three(path, model_size="base"):
        for n in range(3):
            pulled.append(n)
            if n == 1:
                shut()
            yield {"start": n * 1000, "end": n * 1000 + 900, "text": f"line {n}"}

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "iter_segments", three)
    rid = _recording(client)
    return rid, _start(client, rid), pulled


def test_the_per_segment_check_stops_the_transcriber_at_the_next_line(signed_in, monkeypatch):
    """Finding 7: without the `check()` in the segment loop the transcriber
    would be asked for every line after the lock."""
    rid, run, pulled = _three_lines_shut_after_one(signed_in, monkeypatch, spacelock.close_all)
    assert pulled == [0, 1]
    _failed_closed(run, rid)


def test_signing_out_mid_run_fails_it_closed(signed_in, monkeypatch):
    client = signed_in
    token = client.headers["X-Auth-Token"]

    def sign_out():
        got = client.post("/auth/lock")
        assert got.status_code == 200, got.text
        assert not vault.is_granted(token)

    rid, run, pulled = _three_lines_shut_after_one(client, monkeypatch, sign_out)
    assert pulled == [0, 1]
    _failed_closed(run, rid)


def test_the_idle_timeout_mid_run_fails_it_closed(signed_in, monkeypatch):
    """A fixed clock that steps past the idle window as the second line is heard."""
    clock = [1000.0]
    monkeypatch.setattr(spacelock, "_now", lambda: clock[0])
    spacelock.open_for(signed_in.headers["X-Auth-Token"])

    def idle():
        clock[0] += spacelock.idle_minutes() * 60 + 1

    rid, run, pulled = _three_lines_shut_after_one(signed_in, monkeypatch, idle)
    assert pulled == [0, 1]
    _failed_closed(run, rid)


def test_a_document_locked_mid_read_keeps_no_text(signed_in, monkeypatch):
    from tessellate.ai import docreader

    client = signed_in
    aid = _attach_held(client, monkeypatch)
    real = docreader._extract

    def lock_while_reading(path, filename):
        text = real(path, filename)
        assert "boathouse" in text
        spacelock.close_all()
        return text

    monkeypatch.setattr(docreader, "_extract", lock_while_reading)
    _off_request(docreader.read_document_and_store, aid)
    assert _ocr_of(aid)[0] is None
    assert _left_in_tmp() == []


def test_the_token_is_in_no_log_line_event_or_stored_job(signed_in, monkeypatch, caplog):
    import logging

    from sqlalchemy import inspect, text

    from tessellate.ai import docreader

    client = signed_in
    token = client.headers["X-Auth-Token"]
    queued = []
    caplog.set_level(logging.DEBUG)
    _whisper(monkeypatch)
    rid = _recording(client)
    assert _start(client, rid)["state"] == "done"
    aid = _attach_held(client, monkeypatch)
    monkeypatch.setattr(docreader.jobs, "enqueue", lambda *a, **k: queued.append((a, k)) or 0)
    _hand_over(docreader, token, aid)
    assert queued and token not in repr(queued)
    _off_request(docreader.read_document_and_store, aid)
    assert caplog.records and all(token not in record.getMessage() for record in caplog.records)
    engine = deps.get_db().engine
    tables = inspect(engine).get_table_names()
    assert {"audit_log", "jobs"} <= set(tables), tables
    with engine.connect() as conn:
        for table in tables:
            rows = conn.execute(text(f'SELECT * FROM "{table}"')).fetchall()  # noqa: S608  # names from the schema
            assert token not in repr(rows), table


def test_a_job_handed_for_space_a_does_not_read_a_file_now_in_space_b(signed_in, monkeypatch):
    """Finding 5: the token is bound to the space its file was in when it
    was handed over."""
    from sqlalchemy import text

    from tessellate.ai import docreader

    client = signed_in
    other = client.post("/spaces", json={"name": "Other", "is_private": True})
    assert other.status_code == 200, other.text
    aid = _attach_held(client, monkeypatch)
    with deps.get_db().engine.begin() as conn:
        conn.execute(text("UPDATE attachments SET workspace_id = :s WHERE id = :i"), {"s": other.json()["id"], "i": aid})
    _off_request(docreader.read_document_and_store, aid)
    assert _ocr_of(aid)[0] is None
    assert aid not in docreader._HANDED


def test_a_handed_token_is_dropped_when_the_read_fails_and_on_lock_and_sign_out(signed_in, monkeypatch):
    """Finding 5: a handed token never outlives its read, its door or its session."""
    from tessellate.ai import docreader

    client = signed_in
    token = client.headers["X-Auth-Token"]
    aid = _attach_held(client, monkeypatch)
    assert aid in docreader._HANDED  # the upload handed it over

    def broken(*args):
        raise ValueError("a reader that falls over")

    monkeypatch.setattr(docreader, "_read_private", broken)
    _off_request(docreader.read_document_and_store, aid)
    assert aid not in docreader._HANDED
    _hand_over(docreader, token, aid)
    assert aid in docreader._HANDED
    got = client.post("/private-spaces/lock")
    assert got.status_code == 200, got.text
    assert docreader._HANDED == {}
    got = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert got.status_code == 200, got.text
    _hand_over(docreader, token, aid)
    assert aid in docreader._HANDED
    got = client.post("/auth/lock")
    assert got.status_code == 200, got.text
    assert docreader._HANDED == {}
