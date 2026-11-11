"""A private note's words are gone from the file, not only from the answers.

SEC-03 (security audit, 2026-10-05): making a note private removed its
search rows logically (`MATCH` found nothing), but FTS5 only writes delete
markers; the segment blobs kept every token until an automerge happened to
rewrite them. So the vocabulary of a private note (a PIN, a place) was
readable with `strings` from the live database, every `POST /backups` copy
and the `GET /export/backup` zip. The repro's own tokens are used here.
"""

from __future__ import annotations

import io
import sqlite3
import zipfile

import pytest

from tessellate.core import deps, vault
from tessellate.entry import manager_private

SECRET = "# Zebrasecret plan\n\nMy bank PIN is 4417, the spare key is at Quokkatown station."
TOKENS = (b"quokkatown", b"zebrasecret")


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _leaks(raw: bytes) -> list[bytes]:
    lowered = raw.lower()
    return [token for token in TOKENS if token in lowered]


def _with_neighbours(client) -> int:
    # Enough other notes that the private one's tokens share segments with
    # live ones, which is the shape a real notebook has.
    for i in range(12):
        client.post("/entries", json={"content": f"Ordinary note {i} about bread and tea"})
    return client.post("/entries", json={"content": SECRET}).json()["id"]


def _database_bytes() -> bytes:
    data_dir = deps.get_config().data_dir
    raw = b""
    for name in ("tessellate.db", "tessellate.db-wal"):
        path = data_dir / name
        if path.exists():
            raw += path.read_bytes()
    return raw


def test_making_a_note_private_leaves_none_of_its_words_in_the_file(client):
    entry_id = _with_neighbours(client)
    assert _leaks(_database_bytes()), "the test needs the words to be in the file first"
    assert client.post(f"/entries/{entry_id}/privacy", json={"private": True}).status_code == 200
    assert _leaks(_database_bytes()) == []
    # Everything else is still found, and the note itself still opens.
    with sqlite3.connect(deps.get_config().data_dir / "tessellate.db") as db:
        assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH 'bread'").fetchone()[0] == 12
        assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH 'quokkatown'").fetchone()[0] == 0
    assert "Quokkatown" in client.get(f"/entries/{entry_id}").json()["content"]


def test_a_backup_and_the_export_zip_carry_none_of_its_words(client):
    entry_id = _with_neighbours(client)
    client.post(f"/entries/{entry_id}/privacy", json={"private": True})
    made = client.post("/backups")
    assert made.status_code == 201, made.text
    backups = sorted((deps.get_config().data_dir / "backups").glob("tessellate-*.db"))
    assert backups and _leaks(backups[-1].read_bytes()) == []
    exported = client.get("/export/backup")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as zf:
        assert _leaks(zf.read("tessellate.db")) == []


def test_a_backup_strips_what_an_older_version_left_behind(client, session):
    """A notebook whose note went private before this fix still has the words
    in its segments; the backup copy is cleaned on its way out."""
    entry_id = _with_neighbours(client)
    from tessellate.core.database import Entry

    entry = session.get(Entry, entry_id)
    assert manager_private.set_private(session, entry, True)
    session.commit()  # no scrub: what an older version did
    made = client.post("/backups")
    assert made.status_code == 201
    # The one this request made, by the name it returned: two backups in the
    # same second are `<stamp>.db` and `<stamp>-1.db`, and "-" sorts before
    # ".", so the last name in the folder can be the older copy (seen on CI).
    backup = deps.get_config().data_dir / "backups" / made.json()["name"]
    assert _leaks(backup.read_bytes()) == []
    # And the copy is a whole, searchable database.
    with sqlite3.connect(backup) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH 'bread'").fetchone()[0] == 12
