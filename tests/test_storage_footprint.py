"""What the data folder's directories weigh (BACKLOG section 26): `GET /storage`
reports uploads, pictures and backups next to the database, from a cached walk."""

from __future__ import annotations

import os
from tests._app_js import with_pieces

from tessellate.core import deps, diskspace


def _write(folder, name, size):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"x" * size)


def test_dir_bytes_sums_nested_files_and_ignores_links(tmp_path):
    _write(tmp_path / "a", "one", 100)
    _write(tmp_path / "a" / "deep", "two", 50)
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    _write(outside, "big", 10_000)
    try:
        os.symlink(outside, tmp_path / "a" / "link")
    except (OSError, NotImplementedError):
        pass  # a filesystem without symlinks: the other checks still hold
    assert diskspace.dir_bytes(tmp_path / "a", ttl=0) == 150
    assert diskspace.dir_bytes(tmp_path / "missing", ttl=0) == 0


def test_the_walk_is_cached_for_the_ttl(tmp_path):
    _write(tmp_path, "one", 10)
    assert diskspace.dir_bytes(tmp_path) == 10
    _write(tmp_path, "two", 90)
    assert diskspace.dir_bytes(tmp_path) == 10  # still believed
    assert diskspace.dir_bytes(tmp_path, ttl=0) == 100  # measured afresh


def test_storage_reports_the_three_folders(client):
    data = deps.get_config().data_dir
    _write(data / "uploads", "a.pdf", 2000)
    _write(data / "media", "p.png", 300)
    _write(data / "backups", "b.zip", 40)
    diskspace._dir_sizes.clear()
    body = client.get("/storage").json()
    assert body["uploads_bytes"] == 2000
    assert body["media_bytes"] == 300
    assert body["backups_bytes"] == 40


def test_the_notebook_segment_counts_the_write_ahead_log_too(client, monkeypatch):
    """Audit 1029 X17: `database_bytes` was the main file alone, so the bar read
    4 KB beside a 2.9 MB log; it is the sum About health shows (`db_footprint`)."""
    from tessellate.api import routes_debug

    monkeypatch.setattr(routes_debug, "db_footprint", lambda path: {"main_bytes": 4096, "wal_bytes": 2_900_000, "size_bytes": 2_904_096})
    assert client.get("/storage").json()["database_bytes"] == 2_904_096


def test_storage_reports_what_the_installed_extras_weigh(client, monkeypatch):
    """The breakdown's last segment (BACKLOG section 26, the owner: see what an
    optional feature costs before deciding to keep it)."""
    from tessellate.core import extras

    first, second = extras.EXTRAS[0], extras.EXTRAS[1]
    monkeypatch.setattr(extras, "is_installed", lambda extra: extra.id in (first.id, second.id))
    monkeypatch.setitem(extras._footprints, first.id, ("1.0", 5_000))
    monkeypatch.setitem(extras._footprints, second.id, ("2.0", None))  # no size known counts as none
    assert extras.installed_bytes() == 5_000
    body = client.get("/storage")
    assert body.json()["extras_bytes"] == 5_000


def test_the_storage_bar_is_one_recipe():
    """Settings, About draws `GET /storage` as one bar and a legend (DESIGN.md,
    the recipe index): drawn by settings-data.js, styled by a lazy sheet, and
    the old one-line text is gone. Driven in a browser by `storagebar.js`."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    data_js = (root / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    settings_js = with_pieces("settings.js")
    sheet = (root / "frontend" / "css" / "settings-data-lazy.css").read_text(encoding="utf-8")
    assert 'id="storage-bar"' in page and 'role="img"' in page[page.index('id="storage-bar"') - 80 : page.index('id="storage-bar"') + 120]
    assert 'id="storage-legend"' in page and "health-files-size" not in page + settings_js
    assert "renderStorageBreakdown" in settings_js and "/css/settings-data-lazy.css" in data_js
    # Every kind the server reports gets a segment colour, and none is a literal.
    for key in ("database_bytes", "uploads_bytes", "media_bytes", "backups_bytes", "extras_bytes"):
        assert f'"{key}"' in data_js and f'data-kind="{key}"' in sheet
    assert "#" not in "".join(line.split("/*")[0] for line in sheet.splitlines() if "{" in line or ":" in line)
    assert "style=" not in data_js.split("async function renderStorageBreakdown")[1].split("//: The schedule")[0]


def test_the_two_totals_say_what_each_covers():
    """Audit 1029 X17: "Together 684 KB" beside "Data folder 9.3 MB" was
    unexplained; each row now says what it counts."""
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "which leave out the search index, logs and other working files" in page
    assert "The five add up to less than the data folder" in page


def test_files_nothing_uses_are_counted_in_about_and_deleted_only_when_asked():
    # L-ui-modernisation-74: the background pass never deletes uploads (a gallery-only picture is wanted).
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    data_js = (root / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")
    body = data_js.split("renderStorageBreakdown.orphans = async")[1].split("\n};\n")[0]
    assert 'id="media-orphans-row"' in page and 'id="media-orphans-delete"' in page
    assert '"/media/orphans?limit=1"' in body and "confirmDialog(" in body
    assert body.index("confirmDialog(") < body.index('method: "DELETE"')
    assert "skipped_private" in body
    autonomous = (root / "src" / "tessellate" / "ai" / "autonomous.py").read_text(encoding="utf-8")
    assert "delete_orphaned_media" not in autonomous
