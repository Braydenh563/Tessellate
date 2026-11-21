"""Stop on a running pool job, per handler (L-world-class-66, B2).

A handler that has a safe boundary calls `jobs.check_stop()` there: Stop
pressed during the model's call means the result is not stored. The model is
the fake transport (CLAUDE.md 4); the stop is set from inside the call, which
is what a click during the call does.
"""

from __future__ import annotations

import time

from tessellate.ai import captioning, vision_ocr
from tessellate.core import deps, jobs
from tessellate.core.database import MediaUpload


def _upload(filename="a.png") -> int:
    with deps.get_db().session() as session:
        row = MediaUpload(filename=filename, original_name=filename)
        session.add(row)
        session.commit()
        return row.id


def _idle(pool: jobs.Pool, seconds: float = 5.0) -> None:
    ends = time.monotonic() + seconds
    while time.monotonic() < ends and (pool.running_count() or pool.queued_count()):
        time.sleep(0.02)
    assert not pool.running_count() and not pool.queued_count()


def _press_stop() -> None:
    jobs._here.job.stop()


def test_caption_stopped_during_the_model_call_stores_nothing(app_state, fake_ollama, tmp_path, monkeypatch):
    upload_id = _upload()
    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_ollama.capabilities_declared = ["vision"]
    deps.override_ai(ollama=fake_ollama)
    monkeypatch.setattr(captioning, "caption_text", lambda *a, **k: (_press_stop(), "a cat")[1])
    pool = jobs.Pool(widths={"model": 1})
    try:
        pool.enqueue("caption", captioning.caption_and_store, upload_id, image, name="a.png")
        _idle(pool)
    finally:
        pool.shutdown(deadline=2)
    with deps.get_db().session() as check:
        assert not check.get(MediaUpload, upload_id).caption


def test_caption_not_stopped_is_stored(app_state, fake_ollama, tmp_path, monkeypatch):
    upload_id = _upload()
    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_ollama.capabilities_declared = ["vision"]
    deps.override_ai(ollama=fake_ollama)
    monkeypatch.setattr(captioning, "caption_text", lambda *a, **k: "a cat")
    pool = jobs.Pool(widths={"model": 1})
    try:
        pool.enqueue("caption", captioning.caption_and_store, upload_id, image, name="a.png")
        _idle(pool)
    finally:
        pool.shutdown(deadline=2)
    with deps.get_db().session() as check:
        assert check.get(MediaUpload, upload_id).caption == "a cat"


def test_vision_read_stopped_during_the_model_call_stores_nothing(app_state, fake_ollama, tmp_path, monkeypatch):
    upload_id = _upload()
    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_ollama.capabilities_declared = ["vision"]
    deps.override_ai(ollama=fake_ollama)
    monkeypatch.setattr(vision_ocr, "vision_ocr_text", lambda *a, **k: (_press_stop(), "words")[1])
    pool = jobs.Pool(widths={"model": 1})
    try:
        pool.enqueue("vision", vision_ocr.vision_ocr_and_store, upload_id, image, name="a.png")
        _idle(pool)
    finally:
        pool.shutdown(deadline=2)
    with deps.get_db().session() as check:
        assert check.get(MediaUpload, upload_id).vision_ocr_text is None


def test_the_folder_walk_ends_between_files_once_stop_is_pressed():
    from tessellate.api import routes_settings_transfer as transfer

    seen = []

    def work():
        for name in transfer._until_stopped(iter(["a", "b", "c", "d"])):
            seen.append(name)
            if name == "b":
                _press_stop()

    pool = jobs.Pool(widths={"batch": 1})
    try:
        pool.enqueue("import", work, name="folder")
        _idle(pool)
    finally:
        pool.shutdown(deadline=2)
    assert seen == ["a", "b"]


def test_a_stop_with_no_name_refuses_to_pick_one_of_two_running():
    """Two running jobs of one kind and no name: neither is stopped (stopping
    the first would stop one nobody pointed at); a name picks exactly one."""
    import threading

    started, release = threading.Barrier(3), threading.Event()
    stopped = []

    def work(label):  # noqa: ANN001, ANN202
        started.wait(5)
        release.wait(5)
        stopped.append(label)

    pool = jobs.Pool(widths={"batch": 2})
    try:
        pool.enqueue("import", lambda: work("one"), name="one")
        pool.enqueue("import", lambda: work("two"), name="two")
        started.wait(5)
        ok, detail = pool.stop_running("import")
        assert not ok and "More than one" in detail
        ok, _detail = pool.stop_running("import", "two")
        assert ok
    finally:
        release.set()
        _idle(pool)
        pool.shutdown(deadline=2)
