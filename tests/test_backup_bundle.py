"""One file, one password: the whole notebook out and back in (BACKLOG 115 row 10).

`GET /export/backup` has always written the zip; nothing read it back, so a
"full backup" was a file the app could not use. The plan's own test is the
shape of the first one here: export, wipe, import, diff equals zero.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from tessellate.core import backup_bundle, deps


def _notes(client):
    return sorted(e["content"] for e in client.get("/entries?limit=100").json())


def _seed(client):
    for text in ("alpha note", "beta note", "gamma note"):
        assert client.post("/entries", json={"content": text}).status_code == 201
    uploads = deps.get_config().data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "scan.pdf").write_bytes(b"%PDF-1.4 a scanned page")


def _wipe(client):
    for entry in client.get("/entries?limit=100").json():
        client.delete(f"/entries/{entry['id']}")
    (deps.get_config().data_dir / "uploads" / "scan.pdf").unlink()


def test_the_stream_cipher_round_trips_across_chunk_boundaries(tmp_path):
    plain = tmp_path / "plain.bin"
    plain.write_bytes(b"x" * (backup_bundle.CHUNK_BYTES * 2 + 17))
    sealed = tmp_path / "sealed.mmenc"
    backup_bundle.encrypt_file(plain, sealed, "correct horse")
    assert sealed.read_bytes().startswith(backup_bundle.MAGIC)
    assert b"xxxxxxxx" not in sealed.read_bytes()
    out = tmp_path / "out.bin"
    backup_bundle.decrypt_file(sealed, out, "correct horse")
    assert out.read_bytes() == plain.read_bytes()


def test_a_wrong_password_and_a_cut_file_both_fail_loudly(tmp_path):
    plain = tmp_path / "plain.bin"
    plain.write_bytes(b"y" * (backup_bundle.CHUNK_BYTES + 5))
    sealed = tmp_path / "sealed.mmenc"
    backup_bundle.encrypt_file(plain, sealed, "right")
    with pytest.raises(backup_bundle.BundleError):
        backup_bundle.decrypt_file(sealed, tmp_path / "o1", "wrong")
    # Dropping the last chunk must not look like a shorter, valid file.
    data = sealed.read_bytes()
    cut = tmp_path / "cut.mmenc"
    cut.write_bytes(data[: len(data) - (backup_bundle.CHUNK_BYTES // 2)])
    with pytest.raises(backup_bundle.BundleError):
        backup_bundle.decrypt_file(cut, tmp_path / "o2", "right")


def test_export_wipe_import_leaves_nothing_different(client):
    _seed(client)
    before = _notes(client)
    sealed = client.post("/backups/bundle", json={"password": "hunter2hunter2"})
    assert sealed.status_code == 200
    assert sealed.content.startswith(backup_bundle.MAGIC)
    _wipe(client)
    assert _notes(client) == []

    reply = client.post(
        "/backups/bundle/restore",
        files={"file": ("notebook.mmenc", sealed.content)},
        data={"password": "hunter2hunter2"},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["signed_out"] is True
    assert _notes(client) == before
    assert (deps.get_config().data_dir / "uploads" / "scan.pdf").read_bytes().startswith(b"%PDF")


def test_a_plain_zip_restores_too(client):
    _seed(client)
    before = _notes(client)
    plain = client.get("/export/backup").content
    _wipe(client)
    reply = client.post("/backups/bundle/restore", files={"file": ("memorymap_backup.zip", plain)})
    assert reply.status_code == 200, reply.text
    assert _notes(client) == before


def test_a_wrong_password_changes_nothing(client):
    _seed(client)
    sealed = client.post("/backups/bundle", json={"password": "hunter2hunter2"}).content
    client.post("/entries", json={"content": "written after the export"})
    reply = client.post(
        "/backups/bundle/restore",
        files={"file": ("n.mmenc", sealed)},
        data={"password": "not the one"},
    )
    assert reply.status_code == 422
    assert "password" in reply.json()["detail"].lower()
    assert "written after the export" in _notes(client)


def test_an_encrypted_file_without_a_password_asks_for_one(client):
    _seed(client)
    sealed = client.post("/backups/bundle", json={"password": "hunter2hunter2"}).content
    reply = client.post("/backups/bundle/restore", files={"file": ("n.mmenc", sealed)})
    assert reply.status_code == 422
    assert "password" in reply.json()["detail"].lower()


def test_a_zip_that_is_not_a_notebook_is_refused_before_anything_is_touched(client):
    _seed(client)
    junk = io.BytesIO()
    with zipfile.ZipFile(junk, "w") as zf:
        zf.writestr("readme.txt", "not a notebook")
    reply = client.post("/backups/bundle/restore", files={"file": ("x.zip", junk.getvalue())})
    assert reply.status_code == 422
    assert len(_notes(client)) == 3


def test_an_archive_cannot_write_outside_the_data_folder(client):
    _seed(client)
    good = client.get("/export/backup").content
    evil = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as source, zipfile.ZipFile(evil, "w") as zf:
        for name in source.namelist():
            zf.writestr(name, source.read(name))
        zf.writestr("uploads/../../escaped.txt", "nope")
    reply = client.post("/backups/bundle/restore", files={"file": ("x.zip", evil.getvalue())})
    assert reply.status_code == 200, reply.text
    assert not (deps.get_config().data_dir.parent / "escaped.txt").exists()
    assert not (deps.get_config().data_dir / "escaped.txt").exists()


def test_a_restored_zip_cannot_redirect_the_model_or_turn_on_the_network(client):
    """Audit 1028 K9: a zip from someone else carries their settings; the ones
    that decide where notes go stay as they are on this computer."""
    import json

    _seed(client)
    good = client.get("/export/backup").content
    evil = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as source, zipfile.ZipFile(evil, "w") as zf:
        for name in source.namelist():
            if name != backup_bundle.PREFERENCES_MEMBER:
                zf.writestr(name, source.read(name))
        zf.writestr(
            backup_bundle.PREFERENCES_MEMBER,
            json.dumps({"llm_base_url": "http://203.0.113.9:8080", "local_only_ai": False,
                        "web_search_enabled": True, "theme": "dark"}),
        )
    reply = client.post("/backups/bundle/restore", files={"file": ("x.zip", evil.getvalue())})
    assert reply.status_code == 200, reply.text
    prefs = deps.get_config().all_preferences()
    assert prefs.get("llm_base_url", "") == ""
    assert prefs.get("local_only_ai", True) is True
    assert prefs.get("web_search_enabled", False) is False
    assert prefs.get("theme") == "dark"
