"""Stop reaches the backup pass between its steps (L-world-class-29): a stop
asked after the copy, after the check or before the second copy leaves no
file named like a backup, no partial and no record, and the pass is on
`passes.STOPPABLE` so the Activity row offers Stop."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tessellate.core import backup, deps, passes


class _FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001, ANN206
        return cls(2026, 11, 12, 3, 0, 0, tzinfo=timezone.utc)


def _leftovers(config) -> list[str]:
    return sorted(p.name for p in backup.backups_dir(config.data_dir).iterdir())


@pytest.mark.parametrize("stop_at", [1, 2])
def test_a_stop_between_steps_leaves_nothing_behind(client, tmp_path, monkeypatch, stop_at):
    monkeypatch.setattr(backup, "datetime", _FixedClock)
    aside = tmp_path / "drive"
    aside.mkdir()
    client.put("/preferences", json={"backup_copy_dir": str(aside)})
    config = deps.get_config()
    config.db_path.touch()
    before = _leftovers(config)
    asked = []

    def should_stop() -> bool:
        asked.append(1)
        return len(asked) == stop_at

    with pytest.raises(backup.BackupStopped):
        backup.backup_now(config.db_path, config.data_dir, origin="manual", should_stop=should_stop)
    assert len(asked) == stop_at
    assert _leftovers(config) == before
    assert list(aside.iterdir()) == []


def test_without_a_stop_the_backup_is_whole(client, monkeypatch):
    monkeypatch.setattr(backup, "datetime", _FixedClock)
    config = deps.get_config()
    config.db_path.touch()
    path = backup.backup_now(config.db_path, config.data_dir, origin="manual", should_stop=lambda: False)
    assert path.name == "tessellate-20261112-030000.db" and path.stat().st_size > 0


def test_the_backup_pass_is_stoppable_and_ends_without_a_file(client):
    assert "backup" in passes.STOPPABLE
    config = deps.get_config()
    config.db_path.touch()
    before = _leftovers(config)
    passes.reset_for_tests()
    passes._stop.add("backup")
    try:
        passes.RUNNERS["backup"]()
    finally:
        passes.reset_for_tests()
    assert _leftovers(config) == before
