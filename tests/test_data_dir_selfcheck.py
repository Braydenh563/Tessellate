"""The data folder's self-check (INBOX 1573, `core/selfcheck.py`).

The owner: "if the user deletes any files or folders from their data folder,
can the app automatically handle that??". Each test builds a notebook in a
temp data dir, deletes or damages one path the way a file manager would, and
starts the app again on it. Nothing here touches the repo's `data/`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate.core import backup, deps, selfcheck

FIXED = datetime(2026, 11, 3, 9, 30, 0, tzinfo=timezone.utc)
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(selfcheck, "_now", lambda: FIXED)
    selfcheck.reset_for_tests()
    yield
    selfcheck.reset_for_tests()


def _start(data: Path) -> TestClient:
    """A fresh process's view of `data`: new singletons, the AI faked off."""
    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService, FakeOllama

    deps.reset_app_state()
    selfcheck.reset_for_tests()
    backup._boot_checks.clear()
    deps.init_app_state(data_dir=data)
    deps.override_ai(ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=False))
    return _local(TestClient(create_app()))


def _local(client: TestClient) -> TestClient:
    """This computer: the offer is never made to another device."""
    return TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))


def _notebook(client: TestClient, app_state) -> dict:
    """One note with one attached file, and a backup holding both."""
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    headers = {"X-Auth-Token": token}
    note = client.post("/entries", json={"content": "Tomatoes need full sun"}, headers=headers).json()
    attached = client.post(
        f"/entries/{note['id']}/files", files={"file": ("plan.txt", b"rows of six", "text/plain")}, headers=headers
    )
    assert attached.status_code in (200, 201), attached.text
    made = client.post("/backups", headers=headers)
    assert made.status_code == 201, made.text
    deps.get_db().engine.dispose()
    return {"note": note["id"], "backup": made.json()["name"], "data": Path(app_state.data_dir)}


def _unlock(client: TestClient) -> dict:
    reply = client.post("/auth/unlock", json={"password": PASSWORD})
    assert reply.status_code == 200, reply.text
    return {"X-Auth-Token": reply.json()["token"]}


def test_a_deleted_database_is_offered_its_newest_backup_and_restored_on_the_choice(client, app_state):
    book = _notebook(client, app_state)
    for name in ("tessellate.db", "tessellate.db-wal", "tessellate.db-shm"):
        (book["data"] / name).unlink(missing_ok=True)
    again = _start(book["data"])
    status = again.get("/auth/status").json()
    assert status["setup_required"] is True
    offer = status["restore_offer"]
    assert offer["name"] == book["backup"] and offer["notes"] == 1 and offer["reason"] == "missing"
    assert (book["data"] / "tessellate.db").exists(), "the app still starts, on a new empty file"
    lan = TestClient(again.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    assert lan.get("/auth/status").json().get("restore_offer") is None, "another device learns nothing of the backups"
    restored = again.post("/backups/restore", json={"name": offer["name"]})
    assert restored.status_code == 200, restored.text
    status = again.get("/auth/status").json()
    assert status["setup_required"] is False and status["restore_offer"] is None
    headers = _unlock(again)
    entries = again.get("/entries", headers=headers).json()
    assert [e["content"] for e in entries] == ["Tomatoes need full sun"]
    report = again.get("/debug/health", headers=headers).json()["trust"]["self_check"]
    assert report["missing_files"]["count"] == 0, "the report is about the restored notebook"


def test_a_lost_log_beside_the_database_is_offered_the_backup_too(client, app_state):
    """The measured case: a `-wal` that held every write since the last fold-in."""
    book = _notebook(client, app_state)
    (book["data"] / "tessellate.db").unlink()
    (book["data"] / "tessellate.db-wal").unlink(missing_ok=True)
    (book["data"] / "tessellate.db-shm").unlink(missing_ok=True)
    _start(book["data"]).get("/auth/status")  # a first start makes the empty file
    offer = _start(book["data"]).get("/auth/status").json()["restore_offer"]
    assert offer["name"] == book["backup"] and offer["reason"] == "empty"


def test_no_offer_without_a_backup_that_holds_notes(client, app_state):
    data = Path(app_state.data_dir)
    status = _local(client).get("/auth/status").json()
    assert status["setup_required"] is True and status["restore_offer"] is None
    (data / "backups").mkdir(exist_ok=True)
    (data / "backups" / "tessellate-20261101-000000.db").write_bytes(b"x")
    assert _start(data).get("/auth/status").json()["restore_offer"] is None


def test_a_damaged_database_is_kept_aside_and_the_backup_offered(client, app_state):
    book = _notebook(client, app_state)
    junk = b"not a notebook at all" * 500
    (book["data"] / "tessellate.db").write_bytes(junk)
    (book["data"] / "tessellate.db-wal").unlink(missing_ok=True)
    (book["data"] / "tessellate.db-shm").unlink(missing_ok=True)
    again = _start(book["data"])
    kept = book["data"] / "tessellate.db.damaged-20261103-093000"
    assert kept.read_bytes() == junk, "the damaged file is kept byte for byte, never deleted"
    offer = again.get("/auth/status").json()["restore_offer"]
    assert offer["reason"] == "damaged" and offer["kept_as"] == kept.name
    assert again.get("/backups/integrity").json()["ok"] is True, "the new file is not the damaged one"


def test_an_unreadable_preferences_file_is_kept_aside_and_the_app_starts(client, app_state):
    book = _notebook(client, app_state)
    prefs = book["data"] / "preferences.json"
    for raw in (b"\xa0\xff\x00 binary", b"[1, 2, 3]"):
        prefs.write_bytes(raw)
        again = _start(book["data"])
        assert again.get("/health").status_code == 200
        kept = sorted(book["data"].glob("preferences.json.unreadable-*"))
        assert kept and kept[-1].read_bytes() == raw
        headers = _unlock(again)
        report = again.post("/debug/health/self-check", headers=headers).json()
        assert any("preferences.json" in line for line in report["repaired"])
        for path in kept:
            path.unlink()


def test_deleted_folders_are_made_again_and_missing_files_are_listed(client, app_state):
    book = _notebook(client, app_state)
    for name in ("uploads", "backups"):
        for path in sorted((book["data"] / name).iterdir()):
            path.unlink()
        (book["data"] / name).rmdir()
    again = _start(book["data"])
    headers = _unlock(again)
    report = again.post("/debug/health/self-check", headers=headers).json()
    assert (book["data"] / "uploads").is_dir() and (book["data"] / "backups").is_dir()
    assert any("uploads folder was missing" in line for line in report["repaired"])
    assert report["missing_files"]["count"] == 1
    item = report["missing_files"]["items"][0]
    assert item["entry_id"] == book["note"] and item["filename"] == "plan.txt" and item["note"] == "Tomatoes need full sun"
    assert report["at"] == FIXED.isoformat() and report["ok"] is False
    health = again.get("/debug/health", headers=headers).json()
    assert health["trust"]["self_check"]["missing_files"]["count"] == 1


def test_a_folder_the_notebook_never_used_is_made_without_a_word(tmp_path):
    """Measured: a new notebook with no picture was told its media folder had gone."""
    lines = selfcheck.recreate_folders(tmp_path, {"uploads": True, "media": False, "backups": False})
    assert all((tmp_path / name).is_dir() for name in selfcheck.OWNED_FOLDERS)
    assert lines == ["The uploads folder was missing and was made again, empty."]


def test_a_file_where_a_folder_belongs_is_reported_not_moved(tmp_path):
    (tmp_path / "media").write_text("mine")
    lines = selfcheck.recreate_folders(tmp_path)
    assert (tmp_path / "media").read_text() == "mine"
    assert any("media is a file" in line for line in lines)
    assert (tmp_path / "uploads").is_dir() and (tmp_path / "backups").is_dir()


def test_everything_but_the_database_deleted_still_opens_the_notebook(client, app_state):
    book = _notebook(client, app_state)
    for path in sorted(book["data"].iterdir(), reverse=True):
        if path.name.startswith("tessellate.db"):
            continue
        if path.is_dir():
            for inner in sorted(path.rglob("*"), reverse=True):
                inner.unlink() if inner.is_file() else inner.rmdir()
            path.rmdir()
        else:
            path.unlink()
    again = _start(book["data"])
    assert again.get("/auth/status").json()["setup_required"] is False
    headers = _unlock(again)
    assert [e["content"] for e in again.get("/entries", headers=headers).json()] == ["Tomatoes need full sun"]
    report = again.post("/debug/health/self-check", headers=headers).json()
    assert report["missing_files"]["count"] == 1
    assert all((book["data"] / name).is_dir() for name in selfcheck.OWNED_FOLDERS)


def test_a_clean_quit_folds_the_log_into_the_database(client, app_state):
    """The `-wal` held every write of the seeded notebook (4 KB main file,
    2.2 MB log, measured): deleting it lost them all. A clean quit folds it in."""
    _notebook(client, app_state)
    deps.get_db().optimize()
    wal = Path(app_state.db_path).with_name("tessellate.db-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    assert backup.notebook_counts(Path(app_state.db_path))["notes"] == 1


def test_the_check_is_cheap_at_two_thousand_notes(app_state, session, monkeypatch):
    """Cheap means the work does not grow with the notes: a fixed number of
    queries, two directory listings and no file check per row. Counted, not
    timed (a 50 ms bound failed at 140.6 ms on a loaded CI runner, 2026-11-14)."""
    import os

    from sqlalchemy import event

    from tessellate.core.database import Attachment, Entry

    for number in range(2000):
        entry = Entry(content=f"note {number}")
        session.add(entry)
        session.flush()
        if number % 4 == 0:
            session.add(Attachment(entry_id=entry.id, filename=f"f{number}.txt", stored_name=f"s{number}.txt", mime="text/plain", size=1))
    session.commit()
    queries: list[str] = []
    listings: list[str] = []
    file_checks: list[str] = []
    real_scandir = os.scandir

    def scandir(path):
        listings.append(str(path))
        return real_scandir(path)

    def counted(name):
        real = getattr(Path, name)

        def check(self, *a, **k):
            file_checks.append(f"{name} {self}")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, name, check)

    monkeypatch.setattr(selfcheck.os, "scandir", scandir)
    for name in ("exists", "is_file", "is_dir", "stat"):
        counted(name)
    engine = session.get_bind()
    listen = lambda *a: queries.append(a[2])  # noqa: E731
    event.listen(engine, "before_cursor_execute", listen)
    try:
        report = selfcheck.run(app_state, session)
    finally:
        event.remove(engine, "before_cursor_execute", listen)
    assert report["missing_files"]["count"] == 500
    assert len(report["missing_files"]["items"]) == selfcheck.MISSING_LISTED
    # Three "is it in use" probes and the two lists, whatever the note count.
    assert len(queries) <= 5, queries
    assert len(listings) == 2, listings
    # The owned folders' checks only: a file check per attachment would be 500.
    assert len(file_checks) < 4 * len(selfcheck.OWNED_FOLDERS) + 4, file_checks


def test_the_check_runs_in_the_start_up_housekeeping():
    import inspect

    from tessellate.api import app as app_module

    source = inspect.getsource(app_module._startup_maintenance)
    assert source.index("_check_notebook_file") < source.index("_check_data_folder") < source.index("_backup_if_due")


def test_the_offer_and_the_report_have_their_places_and_their_help():
    """The lock screen asks, Settings, About, Health shows the report, and the
    Guide answers "I deleted files" (standing orders 11 and 13)."""
    from tessellate.ai.help_topics_more import MORE_TOPICS
    from tests._app_js import app_js_text

    #: Both are built by script when they are needed, not shipped in
    #: index.html (the boot page is at its element cap), so their ids are read
    #: from the builders.
    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    built = (js / "account-recovery.js").read_text(encoding="utf-8") + (js / "settings-health.js").read_text(encoding="utf-8")
    for element in ("lock-restore-offer", "lock-restore-yes", "lock-restore-no", "health-selfcheck-run", "health-missing"):
        assert f'id: "{element}"' in built
    assert 'help.dataset.helpFor = "health-selfcheck-help"' in built and 'id: "health-selfcheck-help"' in built
    assert "initHelpToggles(row)" in built
    assert "showRestoreOffer(status.restore_offer)" in app_js_text()
    assert 'accountRecovery: ["showRestoreOffer"]' in (js / "lazy-entries.js").read_text(encoding="utf-8")
    recovery = (js / "account-recovery.js").read_text(encoding="utf-8")
    assert 'apiJson("/backups/restore", { method: "POST", body: JSON.stringify({ name: offer.name }) })' in recovery
    health = (js / "settings-health.js").read_text(encoding="utf-8")
    assert 'apiJson("/debug/health/self-check", { method: "POST" })' in health and "paintSelfCheck(trust.self_check)" in health
    topic = next(t for t in MORE_TOPICS if t["id"] == "data-folder-check")
    assert "Check and repair" in topic["body"] and "Restore backup or Start a new notebook" in topic["body"]
