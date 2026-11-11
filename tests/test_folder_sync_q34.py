"""Q34, WORLD_CLASS row 36: two installs converge through a shared folder, with no server.

Two databases (the app's own and a second one made here) stand for two computers; each has its own `State`.
Nothing is real inference or network: the folder is a temp dir.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from tessellate.core import database
from tessellate.core.database import Entry, EntryRevision, utcnow
from tessellate.entry import folder_sync, manager

PASS = "correct horse battery"


@pytest.fixture()
def two(session, tmp_path, monkeypatch):
    """(session A, state A, session B, state B, folder). Home is the test's folder: a sync folder lives in home or on a removable drive."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    other = database.DatabaseManager(tmp_path / "b.db")
    b = other.session()
    folder = tmp_path / "shared"
    folder.mkdir()
    yield session, folder_sync.State(device="aaaa"), b, folder_sync.State(device="bbbb"), folder
    b.close()


def sync(session, state, folder, passphrase=PASS):
    return folder_sync.run(session, state, str(folder), passphrase)


def note(session, text, category="Ideas", tags=None):
    return manager.create_entry(session, text, category, tags or [])


def texts(session):
    return sorted(e.content for e in session.scalars(select(Entry)) if not e.is_deleted)


def edit(session, entry, text, when=None):
    manager.update_entry(session, entry, text)
    if when:
        entry.edited_at = when
    session.commit()


def settle(a, sa, b, sb, folder):
    """Both computers sync twice, so each has read the other's final file."""
    for _ in range(2):
        sync(a, sa, folder)
        sync(b, sb, folder)


def test_a_note_made_on_one_computer_arrives_on_the_other(two):
    a, sa, b, sb, folder = two
    note(a, "Buy lime plaster for the hall", "Home", ["diy"])
    first = sync(a, sa, folder)
    assert first["shared"] == 1 and first["peers"] == 0
    got = sync(b, sb, folder)
    assert got["added"] == 1 and got["peers"] == 1
    arrived = b.scalars(select(Entry)).one()
    assert arrived.content == "Buy lime plaster for the hall"
    assert manager.category_name_for(b, arrived) == "Home"
    assert manager.tags_from_json(arrived.tags) == ["diy"]
    # the same note is not made twice on a second round
    sync(a, sa, folder)
    assert sync(b, sb, folder)["added"] == 0
    assert len(list(b.scalars(select(Entry)))) == 1


def test_an_edit_on_one_computer_reaches_the_other_without_a_conflict(two):
    a, sa, b, sb, folder = two
    n = note(a, "First wording")
    settle(a, sa, b, sb, folder)
    edit(a, n, "Second wording")
    sync(a, sa, folder)
    got = sync(b, sb, folder)
    assert got["updated"] == 1 and got["conflicts"] == 0
    assert texts(b) == ["Second wording"]
    # B's copy was kept in History before it was replaced
    assert [r.content for r in b.scalars(select(EntryRevision))] == ["First wording"]


def test_two_computers_converge_after_edits_on_both(two):
    a, sa, b, sb, folder = two
    one = note(a, "Plan the trip")
    two_ = note(a, "Call the plumber")
    settle(a, sa, b, sb, folder)
    # new notes and an edit on each side, between syncs
    note(a, "From A only")
    note(b, "From B only")
    edit(b, b.scalars(select(Entry).where(Entry.content == "Call the plumber")).one(), "Call the plumber on Monday")
    edit(a, one, "Plan the trip to Wales")
    settle(a, sa, b, sb, folder)
    assert texts(a) == texts(b)
    assert texts(a) == ["Call the plumber on Monday", "From A only", "From B only", "Plan the trip to Wales"]
    assert two_.content == "Call the plumber on Monday"


def test_a_conflicting_edit_keeps_both_versions_once(two):
    a, sa, b, sb, folder = two
    n = note(a, "Original sentence")
    settle(a, sa, b, sb, folder)
    now = utcnow()
    edit(a, n, "Edited on A", now)
    m = b.scalars(select(Entry)).one()
    edit(b, m, "Edited on B", now + timedelta(minutes=5))
    settle(a, sa, b, sb, folder)
    # the later edit won on both computers
    assert texts(a) == texts(b) == ["Edited on B"]
    for session in (a, b):
        history = [r.content for r in session.scalars(select(EntryRevision))]
        assert "Edited on A" in history and "Edited on B" not in history
        assert history.count("Edited on A") == 1
    # reading the same files again adds nothing
    settle(a, sa, b, sb, folder)
    assert len([r for r in a.scalars(select(EntryRevision)) if r.content == "Edited on A"]) == 1
    assert len([r for r in b.scalars(select(EntryRevision)) if r.content == "Edited on A"]) == 1


def test_the_same_tie_is_broken_the_same_way_on_both(two):
    a, sa, b, sb, folder = two
    n = note(a, "Seed")
    settle(a, sa, b, sb, folder)
    stamp = utcnow()
    edit(a, n, "A's words", stamp)
    edit(b, b.scalars(select(Entry)).one(), "B's words", stamp)
    settle(a, sa, b, sb, folder)
    assert texts(a) == texts(b)


def test_a_delete_travels_unless_the_other_side_edited(two):
    a, sa, b, sb, folder = two
    gone = note(a, "Throw this away")
    kept = note(a, "Edited elsewhere")
    settle(a, sa, b, sb, folder)
    manager.soft_delete_entry(a, gone)
    manager.soft_delete_entry(a, kept)
    edit(b, b.scalars(select(Entry).where(Entry.content == "Edited elsewhere")).one(), "Edited elsewhere, still wanted", utcnow() - timedelta(days=1))
    settle(a, sa, b, sb, folder)
    assert "Throw this away" not in texts(b)
    # an edit older than the delete loses to it, but its words wait in the recycle bin
    binned = b.scalars(select(Entry).where(Entry.is_deleted == True)).all()  # noqa: E712
    assert "Edited elsewhere, still wanted" in [e.content for e in binned]


def test_private_notes_never_leave_and_are_never_overwritten(two):
    a, sa, b, sb, folder = two
    secret = note(a, "The safe code is 4821")
    secret.is_private = True
    a.commit()
    note(a, "A plain note")
    out = sync(a, sa, folder)
    assert out["shared"] == 1
    raw = "".join(p.read_text("utf-8") for p in folder.iterdir())
    assert "4821" not in raw and "plain note" not in raw  # sealed, and the private one is not in it at all
    sync(b, sb, folder)
    assert texts(b) == ["A plain note"]


def test_the_file_is_encrypted_and_a_wrong_passphrase_reads_nothing(two):
    a, sa, b, sb, folder = two
    note(a, "Only the right passphrase reads this")
    sync(a, sa, folder)
    (file,) = folder.iterdir()
    sealed = json.loads(file.read_text("utf-8"))
    assert sealed["format"] == folder_sync.FORMAT and "right passphrase" not in file.read_text("utf-8")
    bad = sync(b, sb, folder, "a different passphrase")
    assert bad["unreadable"] == 1 and bad["added"] == 0
    assert texts(b) == []


def test_a_folder_that_is_not_one_and_a_short_passphrase_are_refused(two, tmp_path):
    a, sa, _b, _sb, folder = two
    with pytest.raises(folder_sync.SyncError, match="folder"):
        sync(a, sa, tmp_path / "nope")
    with pytest.raises(folder_sync.SyncError, match="passphrase"):
        sync(a, sa, folder, "short")


def test_state_survives_a_restart(two, tmp_path):
    a, sa, b, sb, folder = two
    note(a, "Remembered")
    sync(a, sa, folder)
    path = tmp_path / "folder_sync_state.json"
    folder_sync.save_state(path, sa)
    again = folder_sync.load_state(path)
    assert again.device == "aaaa" and again.uids == sa.uids and again.base == sa.base
    assert folder_sync.load_state(tmp_path / "missing.json").device != "aaaa"


def test_the_notebooks_own_folder_is_refused(two, tmp_path):
    """A sync file inside the notebook's folder would travel with every copy of it (CodeQL path injection review)."""
    a, sa, _b, _sb, _folder = two
    inside = tmp_path / "notebook" / "sub"
    inside.mkdir(parents=True)
    for chosen in (tmp_path / "notebook", inside):
        with pytest.raises(folder_sync.SyncError, match="outside the notebook"):
            folder_sync.run(a, sa, str(chosen), "correct horse battery", notebook=tmp_path / "notebook")


def test_a_folder_outside_home_and_removable_drives_is_refused(two, tmp_path, monkeypatch):
    """The route takes a path from a request (CodeQL path injection): home and the removable-drive mounts only, judged after links."""
    a, sa, _b, _sb, folder = two
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    (tmp_path / "elsewhere").mkdir()
    with pytest.raises(folder_sync.SyncError, match="home folder or on a removable drive"):
        sync(a, sa, folder)
    (tmp_path / "elsewhere" / "link").symlink_to(folder)
    with pytest.raises(folder_sync.SyncError, match="home folder or on a removable drive"):
        sync(a, sa, tmp_path / "elsewhere" / "link")
