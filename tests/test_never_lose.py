"""Never lose a note: one test per path of WORLD_CLASS 25e.

A change saved at once, a draft across a reload, a deletion kept in the bin for
30 days, and the daily backup restoring. Every clock here is fixed (CLAUDE.md
section 8), never the real one.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from tessellate.core import backup, deps, vault
from tessellate.core.database import Entry
from tests._clock import pin_clock
from tests._frozen_clock import FIXED_NOW

ROOT = Path(__file__).resolve().parents[1]


def _rows(db_path, query):
    """Read through a second, raw connection: what a crash right now would leave on disk."""
    con = sqlite3.connect(db_path)
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def test_a_change_is_on_disk_when_the_save_answers(client, app_state):
    """No debounce and no deferred flush: the answer to a save means a crash after it loses nothing."""
    saved = client.post("/entries", json={"content": "first words"})
    assert saved.status_code == 201
    entry_id = saved.json()["id"]
    query = f"SELECT content FROM entries WHERE id = {entry_id}"
    assert _rows(app_state.db_path, query) == [("first words",)]

    edited = client.put(f"/entries/{entry_id}", json={"content": "second words"})
    assert edited.status_code == 200, edited.text
    assert _rows(app_state.db_path, query) == [("second words",)]
    # The words it replaced are kept as a version in the same breath.
    versions = _rows(app_state.db_path, f"SELECT content FROM entry_revisions WHERE entry_id = {entry_id}")
    assert ("first words",) in versions


def test_a_draft_survives_the_notebook_being_reopened(client, app_state):
    """A draft kept on the server is still there when the app starts again on the same folder."""
    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService, FakeOllama

    made = client.post("/entries", json={"content": "half a thought, not filed yet", "is_draft": True})
    assert made.status_code == 201, made.text
    entry_id = made.json()["id"]
    data_dir = app_state.data_dir

    vault.close()
    deps.reset_app_state()
    deps.init_app_state(data_dir=data_dir)
    deps.override_ai(ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=False))
    reopened = TestClient(create_app())

    again = reopened.get(f"/entries/{entry_id}")
    assert again.status_code == 200, again.text
    assert again.json()["content"] == "half a thought, not filed yet"
    assert again.json()["is_draft"] is True


def test_words_typed_in_the_browser_keep_a_killed_server_spec():
    """Words typed but not saved live in the browser, not on the server, so a
    killed server cannot take them. The Playwright spec that proves it has to
    stay, and name the three boxes."""
    spec = (ROOT / "tests-e2e" / "specs" / "draft-recovery.spec.js").read_text(encoding="utf-8")
    for key in ("captureDraft", "quickNoteDraft", "note-edit-draft"):
        assert key in spec, key
    assert "SIGKILL" in spec


def test_a_deleted_note_stays_in_the_bin_for_thirty_days(client, session, monkeypatch):
    from tessellate.entry import manager_purge

    pin_clock(monkeypatch, FIXED_NOW)
    assert deps.get_config().get_preference("recycle_bin_days", None) == 30
    saved = client.post("/entries", json={"content": "keep me thirty days"}).json()
    client.delete(f"/entries/{saved['id']}")

    def purge_after(days: int) -> int:
        session.get(Entry, saved["id"]).deleted_at = FIXED_NOW - timedelta(days=days)
        session.commit()
        return manager_purge.purge_expired_deleted(session, days=30)

    assert purge_after(29) == 0
    assert [e["id"] for e in client.get("/entries", params={"deleted": True}).json()] == [saved["id"]]
    back = client.post(f"/entries/{saved['id']}/restore")
    assert back.status_code == 200
    assert client.get(f"/entries/{saved['id']}").json()["content"] == "keep me thirty days"

    client.delete(f"/entries/{saved['id']}")
    assert purge_after(31) == 1
    assert client.get("/entries", params={"deleted": True}).json() == []


def test_the_daily_backup_is_taken_once_a_day_and_restores_the_notebook(client, monkeypatch):
    config = deps.get_config()
    pin_clock(monkeypatch, FIXED_NOW)
    for stale in backup.backup_files(config.data_dir):
        stale.unlink()
    client.post("/entries", json={"content": "note before the nightly backup"})

    taken = backup.backup_if_due(config.db_path, config.data_dir)
    assert taken is not None
    # Age it on the fixed clock: 23 hours is not due, 25 hours is.
    for hours, due in ((1, False), (23, False), (25, True)):
        stamp = (FIXED_NOW - timedelta(hours=hours)).timestamp()
        os.utime(taken, (stamp, stamp))
        assert backup.backup_is_due(config.db_path, config.data_dir) is due, hours

    client.post("/entries", json={"content": "note after the nightly backup"})
    restored = client.post("/backups/restore", json={"name": taken.name})
    assert restored.status_code == 200, restored.text
    assert [e["content"] for e in client.get("/entries").json()] == ["note before the nightly backup"]
