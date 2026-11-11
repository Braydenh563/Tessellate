"""Brief 101b: an import resets the bin clock.

A folder export carries each binned note's `deleted_at`. Importing it later
restored that old stamp, so the startup sweep (`purge_expired_deleted`) purged
the note the person had just imported, before they could look at it. The bin
clock for an imported row is the import, not the old binning.
"""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta

from tessellate.api.routes_settings_transfer import _parse_frontmatter
from tessellate.core import deps
from tessellate.core.database import Entry, utcnow
from tessellate.entry import app_import, export_folder, manager


def _zip_of(session) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        export_folder.export(session, deps.get_config().uploads_dir, archive)
    return buffer.getvalue()


def test_a_binned_note_imported_with_an_old_stamp_survives_the_sweep(client, tmp_path):
    session = deps.get_db().session()
    entry = manager.create_entry(session, "a note that was binned long ago")
    manager.soft_delete_entry(session, entry)
    entry.deleted_at = utcnow() - timedelta(days=400)
    session.commit()
    data = _zip_of(session)
    session.close()
    deps.reset_app_state()
    deps.init_app_state(data_dir=tmp_path / "fresh")

    session = deps.get_db().session()
    result = app_import.read("memorymap", [("tessellate-notebook.zip", data)], parse_frontmatter=_parse_frontmatter)
    written = export_folder.write(session, result, deps.get_config().uploads_dir)
    assert written["imported"] == 1
    imported = session.get(Entry, written["ids"][0])
    assert imported.is_deleted is True
    assert imported.deleted_at is not None
    assert utcnow() - imported.deleted_at < timedelta(minutes=5)

    assert manager.purge_expired_deleted(session, 30, deps.get_config().uploads_dir) == 0
    assert session.get(Entry, written["ids"][0]) is not None
    session.close()
