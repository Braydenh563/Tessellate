"""L-world-class-671: Tesseract reads a private space's library pictures in the background.

The read borrows the grant of the session that filed the picture
(`sealed_files.for_background`, SECURITY.md T28), only while that session has
the space open. Captioning and the vision readers never start for a sealed
picture: the AI reads a private space only from a chat opened inside it (T10).
Stubbed OCR call: Tesseract may be absent here (CLAUDE.md 4).
"""

from __future__ import annotations

import io
import logging
import time

import pytest
from sqlalchemy import text

from tessellate.ai import captioning, vision_ocr
from tessellate.core import deps, jobs, ocr, sealed_files, spacelock

PASSWORD = "first-pass"
SECRET = "locker code 4715 behind the boathouse"


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
    client.token = token
    yield client
    spacelock.close_all()
    ocr._HANDED.clear()


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, "PNG")
    return buf.getvalue()


def _upload(client, headers=None):
    got = client.post(
        "/media/upload",
        files={"file": ("scan.png", _png(), "image/png")},
        data={"direct": "true"},
        headers=headers if headers is not None else client.space,
    )
    assert got.status_code == 200, got.text
    return got.json()["id"]


def _raw_ocr(uid):
    with deps.get_db().engine.connect() as conn:
        return conn.execute(text("SELECT ocr_text FROM media_uploads WHERE id = :i"), {"i": uid}).scalar()


def _wait(uid, want_text=True, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        jobs.join_threads(0.2)
        if bool(_raw_ocr(uid)) == want_text:
            return True
    return bool(_raw_ocr(uid)) == want_text


def _settled(seconds=5.0):
    """Wait for the job to end (its plain copy gone), then say what is left."""
    end = time.time() + seconds
    while time.time() < end and _left_in_tmp():
        jobs.join_threads(0.2)
        time.sleep(0.05)
    return _left_in_tmp()


def _left_in_tmp():
    root = deps.get_config().data_dir / "tmp"
    return sorted(p.name for p in root.glob(sealed_files.OPEN_PREFIX + "*")) if root.is_dir() else []


@pytest.fixture()
def readers(monkeypatch):
    """Stub Tesseract and trip-wire the AI readers."""
    seen = {"read": [], "ai": []}

    def fake(path, choice=""):
        seen["read"].append(open(path, "rb").read()[:4])
        return SECRET

    monkeypatch.setattr(ocr, "extract_text", fake)
    monkeypatch.setattr(captioning, "caption_in_background", lambda *a, **k: seen["ai"].append("caption"))
    monkeypatch.setattr(vision_ocr, "vision_ocr_in_background", lambda *a, **k: seen["ai"].append("vision"))
    monkeypatch.setattr(vision_ocr, "pdf_vision_ocr_in_background", lambda *a, **k: seen["ai"].append("pdf"))
    return seen


def test_a_sealed_picture_is_read_by_tesseract_in_the_background_and_kept_sealed(signed_in, readers):
    uid = _upload(signed_in)
    assert _wait(uid)
    raw = _raw_ocr(uid)
    assert raw and SECRET not in raw  # stored sealed, not plain
    assert readers["read"] == [b"\x89PNG"]  # the plain copy, not ciphertext
    assert readers["ai"] == []  # no caption, no vision read
    assert _settled() == []
    assert uid not in ocr._HANDED


def test_with_no_session_the_picture_waits_as_before(signed_in, readers):
    # An upload by a request with no granted session cannot hand anything over.
    assert ocr.extract_private_in_background(1, deps.get_config().data_dir / "x.png", "w") is False
    assert ocr._HANDED == {}
    assert readers["read"] == []


def test_a_lock_mid_run_keeps_nothing_and_removes_the_copy(signed_in, monkeypatch, readers):
    import threading

    started, go_on = threading.Event(), threading.Event()

    def slow(path, choice=""):
        started.set()
        go_on.wait(5)
        return SECRET

    monkeypatch.setattr(ocr, "extract_text", slow)
    uid = _upload(signed_in)
    assert started.wait(5)
    assert len(_left_in_tmp()) == 1
    assert signed_in.post("/private-spaces/lock").status_code == 200
    go_on.set()
    assert _settled() == []
    assert not _raw_ocr(uid)
    assert readers["ai"] == []


def test_the_door_is_asked_again_before_the_write(signed_in, monkeypatch, readers):
    def read_then_lock(path, choice=""):
        spacelock.close_all()
        return SECRET

    monkeypatch.setattr(ocr, "extract_text", read_then_lock)
    uid = _upload(signed_in)
    assert _settled() == []
    assert not _raw_ocr(uid)


def test_the_token_is_in_no_log_no_row_and_no_queued_job(signed_in, readers, caplog):
    caplog.set_level(logging.DEBUG)
    seen_args = []
    real = jobs.enqueue

    def spy(kind, fn, *args, **kw):
        seen_args.append((args, kw))
        return real(kind, fn, *args, **kw)

    jobs.enqueue = spy
    try:
        uid = _upload(signed_in)
        assert _wait(uid)
    finally:
        jobs.enqueue = real
    token = signed_in.token
    assert all(token not in repr(a) + repr(k) for a, k in seen_args)
    assert token not in caplog.text


def test_the_handed_token_goes_when_the_session_locks(signed_in, monkeypatch, readers):
    monkeypatch.setattr(jobs, "enqueue", lambda *a, **k: None)  # nothing runs: only the hand-over
    uid = _upload(signed_in)
    assert uid in ocr._HANDED
    signed_in.post("/private-spaces/lock")
    assert uid not in ocr._HANDED


def test_a_picture_in_another_space_is_not_read_with_this_hand(signed_in, readers):
    uid = _upload(signed_in)
    assert _wait(uid)
    ocr._HANDED[uid] = ("t", "some-other-space")
    ocr.extract_private_and_store(uid, deps.get_config().data_dir / "media" / "gone.png")
    assert uid not in ocr._HANDED
