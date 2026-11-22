"""L-world-class-891: a folder import is sent in parts. A 5,000-file vault was
one multipart body the page took 1.4s to build, and it was built twice (the
preview, then the import). Parts go to `POST /import/app/batches/{id}` and the
preview and the import both read the staged files with `?batch=`, so the
reader sees the whole vault at once, as one request did."""

from __future__ import annotations

from pathlib import Path

from tessellate.api import routes_import
from tessellate.core import deps


def _part(names):
    return [("files", (f"vault/{n}.md", f"# {n}\n\nsee [[{names[0]}]]".encode(), "text/markdown")) for n in names]


def _staged(batch: str) -> Path:
    return Path(deps.get_config().data_dir) / routes_import.BATCH_DIR / batch


def test_parts_import_as_one_vault_and_the_import_clears_them(client):
    batch = client.post("/import/app/batches").json()["batch"]
    got = client.post(f"/import/app/batches/{batch}", files=_part(["a", "b"]))
    assert got.json() == {"files": 2}
    got = client.post(f"/import/app/batches/{batch}", files=_part(["c"]))
    assert got.json() == {"files": 3}
    seen = client.post(f"/import/app?source=obsidian&dry_run=1&batch={batch}")
    assert seen.status_code == 200 and seen.json()["found"] == 3
    assert _staged(batch).is_dir(), "the preview keeps the parts for the import"
    done = client.post(f"/import/app?source=obsidian&batch={batch}", data={"exclude": '["vault/b.md"]'})
    assert done.status_code == 201, done.text[:200]
    assert done.json()["imported"] == 2
    assert not _staged(batch).exists()
    got = client.post(f"/import/app?source=obsidian&batch={batch}")
    assert got.status_code == 404


def test_caps_hold_over_every_part(client, monkeypatch):
    monkeypatch.setattr(routes_import, "MAX_FILES", 3)
    batch = client.post("/import/app/batches").json()["batch"]
    got = client.post(f"/import/app/batches/{batch}", files=_part(["a", "b"]))
    assert got.status_code == 200
    over = client.post(f"/import/app/batches/{batch}", files=_part(["c", "d"]))
    assert over.status_code == 422 and "more than one import takes (3)" in over.json()["detail"]


def test_a_bad_or_gone_batch_is_a_404_and_cancel_drops_it(client):
    for bad in ("a" * 32, "XYZ"):
        got = client.post(f"/import/app/batches/{bad}", files=_part(["a"]))
        assert got.status_code == 404
    # A path never reaches the folder: the id is 32 hex characters or nothing.
    import pytest
    from fastapi import HTTPException

    for bad in ("../../etc", "..", "/tmp", "a" * 31 + "/"):
        with pytest.raises(HTTPException):
            routes_import._batch(bad)
    batch = client.post("/import/app/batches").json()["batch"]
    client.post(f"/import/app/batches/{batch}", files=_part(["a"]))
    got = client.delete(f"/import/app/batches/{batch}")
    assert got.status_code == 204
    assert not _staged(batch).exists()
    got = client.post(f"/import/app?source=obsidian&batch={batch}")
    assert got.status_code == 404


def test_files_and_a_batch_together_are_refused(client):
    batch = client.post("/import/app/batches").json()["batch"]
    both = client.post(f"/import/app?source=obsidian&batch={batch}", files=_part(["a"]))
    assert both.status_code == 422


def test_a_batch_left_a_day_ago_goes_when_the_next_opens(client):
    import os
    import time

    old = client.post("/import/app/batches").json()["batch"]
    stamp = time.time() - routes_import.BATCH_KEEP_SECONDS - 60
    os.utime(_staged(old), (stamp, stamp))
    client.post("/import/app/batches")
    assert not _staged(old).exists()
