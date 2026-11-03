"""Restore says what it will bring back before it replaces anything (audit 1028 S69).

The confirm read "Restore this backup?" with no way to tell a backup of last
week's 400 notes from an empty one. GET /backups/summary counts the backup's
notes and documents next to the live notebook's, read-only, so the confirm
can say "412 notes and 9 documents (now 430 and 9)".
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core import backup


def _save(client, content):
    response = client.post("/entries", json={"content": content})
    assert response.status_code == 201
    return response.json()


def test_the_summary_counts_the_backup_and_the_live_notebook(client):
    _save(client, "first")
    _save(client, "second")
    name = client.post("/backups").json()["name"]
    _save(client, "after the backup")

    response = client.get("/backups/summary", params={"name": name})
    assert response.status_code == 200
    body = response.json()
    assert body["backup"]["notes"] == body["live"]["notes"] - 1
    assert body["backup"]["documents"] == body["live"]["documents"]


def test_a_binned_note_is_not_counted(client):
    note = _save(client, "going to the bin")
    before = client.get("/backups/summary", params={"name": client.post("/backups").json()["name"]}).json()
    client.delete(f"/entries/{note['id']}")
    after = client.get("/backups/summary", params={"name": client.post("/backups").json()["name"]}).json()
    assert after["backup"]["notes"] == before["backup"]["notes"] - 1


def test_an_unknown_or_outside_name_is_not_found(client):
    assert client.get("/backups/summary", params={"name": "nope.db"}).status_code == 404
    assert client.get("/backups/summary", params={"name": "../tessellate.db"}).status_code == 404


def test_an_unreadable_file_gives_no_counts_rather_than_an_error(tmp_path: Path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database")
    assert backup.notebook_counts(junk) is None
