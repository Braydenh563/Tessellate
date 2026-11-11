"""Sync through a folder (WORLD_CLASS_PLAN B6 decision 14, row 36): two installs converge with no server.

Two data folders (`Notebook` from `tests/test_sync_segments.py`) stand for two computers; the shared folder is a
temp dir. The file carries the home-network segments, manifest and items, and is read through
`sync_pull.pull_from`, so these tests hold the folder to the same rules as the LAN tests. Times are stamped by
the test, never read off the clock.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.core import vault
from tessellate.core.database import Attachment, Document, Entry, EntryRevision
from tessellate.entry import folder_sync, manager, sync_pull
from tests.test_sync_segments import Link, Notebook

PASS = "correct horse battery"


def _at(minute: int) -> datetime:
    return datetime(2026, 11, 1, 12, minute)


@pytest.fixture()
def two(app_state, tmp_path):
    """(notebook A, notebook B, folder)."""
    a, b = Notebook(tmp_path, "a"), Notebook(tmp_path, "b")
    folder = tmp_path / "shared"
    folder.mkdir()
    yield a, b, folder
    for book in (a, b):
        book.session.close()
    vault.close()


def sync(book: Notebook, folder, passphrase: str = PASS) -> dict:
    book.session.expire_all()
    return folder_sync.run(book.session, book.dir, str(folder), passphrase)


def note(book: Notebook, text: str, minute: int, category: str = "Ideas", tags=None) -> Entry:
    entry = manager.create_entry(book.session, text, category, tags or [])
    return book.stamp(entry, minute)


def find(book: Notebook, text: str) -> Entry:
    book.session.expire_all()
    return book.session.scalars(select(Entry).where(Entry.content == text)).one()


def edit(book: Notebook, entry: Entry, text: str, minute: int) -> None:
    manager.update_entry(book.session, entry, text)
    book.stamp(entry, minute)


def texts(book: Notebook) -> list[str]:
    return sorted(e.content for e in book.notes() if not e.is_deleted)


def history(book: Notebook) -> list[str]:
    book.session.expire_all()
    return list(book.session.scalars(select(EntryRevision.content)))


def settle(a: Notebook, b: Notebook, folder) -> None:
    """Both computers sync twice, so each has read the other's final file."""
    for _ in range(2):
        sync(a, folder)
        sync(b, folder)


def test_a_note_made_on_one_computer_arrives_on_the_other(two):
    a, b, folder = two
    note(a, "Buy lime plaster for the hall", 1, "Home", ["diy"])
    first = sync(a, folder)
    assert first["shared"] == 1 and first["peers"] == 0
    got = sync(b, folder)
    assert got["applied"] == 1 and got["peers"] == 1 and got["error"] == ""
    arrived = find(b, "Buy lime plaster for the hall")
    assert manager.category_name_for(b.session, arrived) == "Home"
    assert manager.tags_from_json(arrived.tags) == ["diy"]
    # the same note is not made twice on a second round
    sync(a, folder)
    assert sync(b, folder)["applied"] == 0
    assert len(b.notes()) == 1


def test_an_edit_on_one_computer_reaches_the_other_without_a_conflict(two):
    a, b, folder = two
    n = note(a, "First wording", 1)
    settle(a, b, folder)
    edit(a, n, "Second wording", 3)
    sync(a, folder)
    got = sync(b, folder)
    assert got["applied"] == 1 and got["conflicts"] == 0
    assert texts(b) == ["Second wording"]
    # B's copy was kept in History before it was replaced
    assert history(b) == ["First wording"]


def test_two_computers_converge_after_edits_on_both(two):
    a, b, folder = two
    one = note(a, "Plan the trip", 1)
    note(a, "Call the plumber", 1)
    settle(a, b, folder)
    # new notes and an edit on each side, between syncs
    note(a, "From A only", 2)
    note(b, "From B only", 2)
    edit(b, find(b, "Call the plumber"), "Call the plumber on Monday", 3)
    edit(a, one, "Plan the trip to Wales", 3)
    settle(a, b, folder)
    assert texts(a) == texts(b) == ["Call the plumber on Monday", "From A only", "From B only", "Plan the trip to Wales"]


def test_a_conflicting_edit_keeps_both_versions_once(two):
    a, b, folder = two
    n = note(a, "Original sentence", 1)
    settle(a, b, folder)
    edit(a, n, "Edited on A", 3)
    edit(b, find(b, "Original sentence"), "Edited on B", 5)
    settle(a, b, folder)
    # the later edit won on both computers, and A's words are in History on both, once
    assert texts(a) == texts(b) == ["Edited on B"]
    for book in (a, b):
        kept = history(book)
        assert kept.count("Edited on A") == 1 and "Edited on B" not in kept
    # reading the same files again adds nothing
    settle(a, b, folder)
    assert history(a).count("Edited on A") == 1 and history(b).count("Edited on A") == 1


def test_the_same_tie_is_broken_the_same_way_on_both(two):
    a, b, folder = two
    n = note(a, "Seed", 1)
    settle(a, b, folder)
    edit(a, n, "A's words", 4)
    edit(b, find(b, "Seed"), "B's words", 4)
    settle(a, b, folder)
    assert texts(a) == texts(b)


def test_a_delete_travels_and_an_older_edit_on_the_other_waits_in_history(two):
    a, b, folder = two
    gone = note(a, "Throw this away", 1)
    kept = note(a, "Edited elsewhere", 1)
    settle(a, b, folder)
    edit(b, find(b, "Edited elsewhere"), "Edited elsewhere, still wanted", 4)
    for entry in (gone, kept):
        manager.soft_delete_entry(a.session, entry)
        a.stamp(entry, 6)
    settle(a, b, folder)
    assert texts(b) == texts(a) == []
    # the edit older than the delete loses to it, but its words wait in the binned note's History
    assert "Edited elsewhere, still wanted" in history(b)


def test_private_notes_never_leave_and_are_never_overwritten(two):
    a, b, folder = two
    secret = note(a, "The safe code is 4821", 1)
    secret.is_private = True
    a.session.commit()
    note(a, "A plain note", 2)
    assert sync(a, folder)["shared"] == 1
    raw = "".join(p.read_text("utf-8") for p in folder.glob("*.json"))
    assert "4821" not in raw and "plain note" not in raw  # sealed, and the private one is not in it at all
    sync(b, folder)
    assert texts(b) == ["A plain note"]


def test_the_file_is_encrypted_and_a_wrong_passphrase_reads_nothing(two):
    a, b, folder = two
    note(a, "Only the right passphrase reads this", 1)
    sync(a, folder)
    (file,) = folder.glob("*.json")
    sealed = json.loads(file.read_text("utf-8"))
    assert sealed["format"] == folder_sync.FORMAT and "right passphrase" not in file.read_text("utf-8")
    bad = sync(b, folder, "a different passphrase")
    assert bad["unreadable"] == 1 and bad["applied"] == 0
    assert texts(b) == []


def test_a_folder_that_is_not_one_and_a_short_passphrase_are_refused(two, tmp_path):
    a, _b, folder = two
    with pytest.raises(folder_sync.SyncError, match="folder"):
        sync(a, tmp_path / "nope")
    with pytest.raises(folder_sync.SyncError, match="passphrase"):
        sync(a, folder, "short")


def test_the_folder_and_time_are_remembered_and_the_device_is_the_networks(two):
    a, _b, folder = two
    assert folder_sync.load_state(a.dir) == {"folder": "", "last": ""}
    sync(a, folder)
    remembered = folder_sync.load_state(a.dir)
    assert remembered["folder"] == str(folder) and remembered["last"]
    assert PASS not in folder_sync.state_path(a.dir).read_text("utf-8")
    assert (folder / f"tessellate-sync-{a.device}.json").is_file()


# --- decision 14: the folder is a transport of the one apply path -------------------


def test_documents_boards_and_files_come_through_the_folder_and_a_removal_follows(two):
    a, b, folder = two
    receipt = note(a, "Receipt", 1)
    a.session.add(Document(title="Boiler", content="Service in March.", updated_at=_at(2)))
    a.session.add(Entry(content="Garden plan", is_board=True, updated_at=_at(2)))
    (a.dir / "uploads").mkdir()
    (a.dir / "uploads" / "r.bin").write_bytes(b"\x89PNG receipt bytes")
    a.session.add(Attachment(entry_id=receipt.id, filename="receipt.png", stored_name="r.bin", mime="image/png", size=18))
    a.session.commit()
    sync(a, folder)
    assert b"receipt bytes" not in b"".join(p.read_bytes() for p in folder.rglob("*") if p.is_file())
    got = sync(b, folder)
    assert got["error"] == "" and got["applied"] == 4  # the note, the document, the board, the file
    b.session.expire_all()
    [doc] = b.session.scalars(select(Document)).all()
    [copy] = b.session.scalars(select(Attachment)).all()
    assert (doc.title, doc.content) == ("Boiler", "Service in March.")
    assert [e.content for e in b.notes() if e.is_board] == ["Garden plan"]
    assert (b.dir / "uploads" / copy.stored_name).read_bytes() == b"\x89PNG receipt bytes"
    assert sync(b, folder)["applied"] == 0
    # removed on A: its sealed copy leaves the folder and B removes its own
    a.session.delete(a.session.scalars(select(Attachment)).one())
    a.session.commit()
    sync(a, folder)
    assert list((folder / f"tessellate-sync-{a.device}-files").iterdir()) == []
    sync(b, folder)
    b.session.expire_all()
    assert b.session.scalars(select(Attachment)).all() == []


def test_a_private_document_stays_home(two):
    a, b, folder = two
    vault.close()
    from tessellate.core import crypto

    vault.set_key(crypto.new_dek())
    a.session.add(Document(title="Safe", content="The code is 4412", is_private=True, updated_at=_at(1)))
    a.session.commit()
    sync(a, folder)
    got = sync(b, folder)
    b.session.expire_all()
    assert got["error"] == "" and b.session.scalars(select(Document)).all() == []


def test_a_note_that_came_over_the_network_is_not_doubled_by_the_folder_and_the_line_is_shared(two, monkeypatch):
    a, b, folder = two
    note(a, "Shared both ways", 1)
    monkeypatch.setattr(sync_pull, "_transport", lambda: Link(a))
    b.session.expire_all()
    assert sync_pull.pull(b.session, b.dir)["via"] == "network"
    sync(a, folder)
    assert sync(b, folder)["applied"] == 0 and texts(b) == ["Shared both ways"]
    line = sync_pull.status(b.dir)
    assert line["via"] == "folder" and line["synced_at"] and line["error"] == ""
