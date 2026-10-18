"""Backup rows say which is latest, what made each, its size and whether it
was checked (INBOX 804 and 805, the owner: "it is unclear which backup is the
latest, and also the backups need more file info and details")."""

from __future__ import annotations

import os

from tessellate.core import backup, deps


def test_each_backup_records_what_made_it_and_that_it_was_checked(app_state):
    config = deps.get_config()
    config.db_path.touch()
    path = backup.backup_now(config.db_path, config.data_dir, origin="manual")
    row = next(b for b in backup.list_backups(config.data_dir) if b["name"] == path.name)
    assert row["origin"] == "manual" and row["origin_words"] == "Made by you"
    assert row["checked"] is True and row["latest"] is True


def test_an_old_backup_with_no_record_is_still_listed_and_says_so(app_state):
    config = deps.get_config()
    folder = backup.backups_dir(config.data_dir)
    old = folder / "memorymap-20260101-010000.db"
    old.write_bytes(b"x")
    os.utime(old, (1_700_000_000, 1_700_000_000))
    row = next(b for b in backup.list_backups(config.data_dir) if b["name"] == old.name)
    assert row["origin"] == "" and row["origin_words"] == "" and row["checked"] is None


def test_only_the_newest_is_latest(app_state):
    config = deps.get_config()
    config.db_path.touch()
    backup.backup_now(config.db_path, config.data_dir, origin="daily")
    newest = backup.backup_now(config.db_path, config.data_dir, origin="manual")
    rows = backup.list_backups(config.data_dir)
    assert [r["name"] for r in rows if r["latest"]] == [newest.name]


def test_pruning_and_deleting_take_the_record_with_the_backup(client):
    config = deps.get_config()
    name = client.post("/backups").json()["name"]
    sidecar = backup.backups_dir(config.data_dir) / f"{name}.json"
    assert sidecar.is_file()
    client.delete(f"/backups/{name}")
    assert not sidecar.exists()
    for _ in range(3):
        backup.backup_now(config.db_path, config.data_dir, origin="manual")
    backup.prune(config.data_dir, 1)
    records = list(backup.backups_dir(config.data_dir).glob("*.json"))
    assert len(records) == 1


def test_the_safety_copy_before_a_restore_says_so(client):
    config = deps.get_config()
    name = client.post("/backups").json()["name"]
    client.post("/backups/restore", json={"name": name})
    words = {b["origin_words"] for b in backup.list_backups(config.data_dir)}
    assert "Before a restore" in words


def test_the_backups_group_shows_its_schedule_with_the_last_success():
    """The schedule line (WORLD_CLASS 25e, data-1011): above the list, filled
    from the job record, saying whether the last run worked and when the next
    is due."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    script = (root / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    assert page.index('id="backup-schedule"') < page.index('id="backup-list"')
    assert "function backupScheduleWords" in script and "/jobs/last-runs" in script
    assert "The last try failed" in script and "Next due" in script
    assert "the line above the list says when the last one" in page  # the ? popover names it


def test_the_backup_row_shows_origin_and_verified_as_badges():
    """The facts are badges (origin, verified), not one grey sentence, so the
    latest backup and a checked one read at a glance."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "frontend/js/settings-data.js").read_text(encoding="utf-8")
    assert "Verified" in text and "Not verified" in text
    assert "checked: it opens and reads back" not in text
