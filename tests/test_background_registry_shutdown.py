"""The registry of non-job threads (`jobs.thread`, was `core/background.py`) is asked to stop at
quit (bug sweep 2026-10-12): `stop_all` existed and nothing called it, so a
watcher it listed (the embedder's idle watch) was left to die with the
process. test_activity's THREAD_SITES names the registry as the way its
threads reach Activity and shutdown."""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from tessellate.core import jobs


def test_a_quit_asks_every_registered_thread_to_stop(app_state):
    from tessellate.api.app import create_app

    asked = threading.Event()
    jobs.thread("test-watch", lambda: asked.wait(10), stop=asked.set)
    try:
        with TestClient(create_app()):
            assert any(row["name"] == "test-watch" for row in jobs.threads())
        assert asked.is_set()
    finally:
        asked.set()
