"""Sync as log shipping between two data folders (WORLD_CLASS_PLAN B6, events-sync).

Two notebooks, each its own data folder and SQLite file, pull from each other
through `sync_pull.pull` over a fake transport: the segment goes through JSON
as it would over the wire, and nothing else is shared. What a real pair of
computers adds (the LAN fetch, the sign-in it carries) is not built; see the
plan's decision 4 and the module docstring of `entry/sync_pull.py`.

Times are fixed: every note's `updated_at` is stamped by the test, never read
off the clock, because the later stamp is what decides a conflict.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from tessellate.core import crypto, sync_state, vault
from tessellate.core.database import DatabaseManager, Entry, EntryRevision
from tessellate.entry import manager, sync_pull, sync_segments
from tessellate.entry.manager_private import set_private


def _at(minute: int) -> datetime:
    return datetime(2026, 11, 1, 12, minute, tzinfo=timezone.utc)


class Notebook:
    def __init__(self, root: Path, name: str) -> None:
        self.dir = root / name
        self.dir.mkdir()
        self.session = DatabaseManager(self.dir / "memorymap.db").session()
        self.device = sync_state.device_id(self.dir)

    def write(self, text: str, minute: int) -> Entry:
        entry = manager.create_entry(self.session, text)
        return self.stamp(entry, minute)

    def stamp(self, entry: Entry, minute: int) -> Entry:
        entry.updated_at = _at(minute)
        self.session.commit()
        return entry

    def notes(self) -> list[Entry]:
        self.session.expire_all()
        return list(self.session.scalars(select(Entry).order_by(Entry.id)))

    def texts(self) -> list[str]:
        return sorted(e.content for e in self.notes())


class Link:
    """The fake transport: the other notebook's export, through JSON."""

    def __init__(self, source: Notebook) -> None:
        self.source = source
        self.name = source.device
        self.fail: Exception | None = None
        self.tamper = False
        self.fetches = 0

    def fetch(self, since: int, me: str) -> dict:
        self.fetches += 1
        if self.fail:
            raise self.fail
        segment = json.loads(json.dumps(sync_segments.export_segment(self.source.session, self.name, since, me)))
        if self.tamper and segment["notes"]:
            segment["notes"][0]["content"] += " (changed on the way)"
        return segment


@pytest.fixture()
def pair(app_state, tmp_path, monkeypatch):
    a, b = Notebook(tmp_path, "a"), Notebook(tmp_path, "b")
    links = {a.dir: Link(b), b.dir: Link(a)}
    current = {}
    monkeypatch.setattr(sync_pull, "_transport", lambda: current.get("link"))

    def pull(into: Notebook) -> dict:
        current["link"] = links[into.dir]
        return sync_pull.pull(into.session, into.dir)

    yield a, b, pull, links
    for book in (a, b):
        book.session.close()
    vault.close()


def test_a_note_written_on_one_reaches_the_other_and_a_second_pull_changes_nothing(pair):
    a, b, pull, _ = pair
    a.write("Boiler service is due in March", 1)
    first = pull(b)
    assert first["error"] == "" and first["applied"] == 1
    assert b.texts() == ["Boiler service is due in March"]
    again = pull(b)
    assert again["error"] == "" and again["applied"] == 0
    assert len(b.notes()) == 1


def test_an_edit_on_the_other_side_comes_back_and_is_not_echoed(pair):
    a, b, pull, links = pair
    a.write("Plant the tulips", 1)
    pull(b)
    received = b.notes()[0]
    manager.update_entry(b.session, received, content="Plant the tulips in October")
    b.stamp(received, 5)
    assert pull(a)["applied"] == 1
    assert a.texts() == ["Plant the tulips in October"]
    # A's own apply is attributed to B and is not shipped back to B.
    since = sync_state.peer(b.dir, a.device)["cursor"]
    assert sync_segments.export_segment(a.session, a.device, since, b.device)["notes"] == []
    assert pull(b)["applied"] == 0 and b.texts() == ["Plant the tulips in October"]


def test_edits_on_both_computers_the_later_wins_and_no_words_are_lost(pair):
    a, b, pull, _ = pair
    note = a.write("Meeting at ten", 1)
    pull(b)
    theirs = b.notes()[0]
    manager.update_entry(a.session, note, content="Meeting at ten, room 4")
    a.stamp(note, 3)
    manager.update_entry(b.session, theirs, content="Meeting moved to eleven")
    b.stamp(theirs, 7)
    b_side = pull(b)  # A's change is the earlier one: B keeps its own and files A's as a version
    assert b_side["conflicts"] == 1 and b.texts() == ["Meeting moved to eleven"]
    assert pull(a)["applied"] == 1 and a.texts() == ["Meeting moved to eleven"]
    for book, entry_id in ((a, a.notes()[0].id), (b, b.notes()[0].id)):
        kept = set(book.session.scalars(select(EntryRevision.content).where(EntryRevision.entry_id == entry_id)))
        assert "Meeting at ten, room 4" in kept, book.dir.name


def test_a_binned_note_lands_in_the_other_bin_not_gone(pair):
    a, b, pull, _ = pair
    note = a.write("Old shopping list", 1)
    pull(b)
    manager.soft_delete_entry(a.session, note)
    a.stamp(note, 4)
    assert pull(b)["applied"] == 1
    [copy] = b.notes()
    assert copy.is_deleted and copy.deleted_at is not None and copy.content == "Old shopping list"


def test_a_private_note_ships_as_ciphertext_and_the_key_stays_home(pair):
    a, b, pull, links = pair
    vault.close()
    vault.create(a.session, "a-passphrase")
    note = a.write("The safe code is 4412", 1)
    assert set_private(a.session, note, True)
    a.stamp(note, 2)
    segment = links[b.dir].fetch(0, b.device)
    assert "4412" not in json.dumps(segment)
    assert pull(b)["applied"] == 1
    [copy] = b.notes()
    assert copy.is_private and copy.content == note.content and crypto.is_encrypted(copy.content)
    vault.set_key(crypto.new_dek())  # B's own key: a different notebook's data key
    assert manager.readable_content(copy) == "This private note couldn't be decrypted."


def test_a_segment_cut_off_part_way_is_applied_again_without_duplicates(pair, monkeypatch):
    a, b, pull, _ = pair
    for minute, text in enumerate(("one", "two", "three"), start=1):
        a.write(text, minute)
    real = sync_segments._apply_one
    calls = {"n": 0}

    def crash_on_the_second(*args):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("power cut")
        return real(*args)

    monkeypatch.setattr(sync_segments, "_apply_one", crash_on_the_second)
    stopped = pull(b)
    assert stopped["error"] == sync_pull.STOPPED
    assert b.texts() == ["one"]
    assert sync_state.peer(b.dir, a.device)["cursor"] == 0
    monkeypatch.setattr(sync_segments, "_apply_one", real)
    resumed = pull(b)
    assert resumed["error"] == "" and b.texts() == ["one", "three", "two"]
    assert len(b.notes()) == 3


def test_a_damaged_segment_is_refused_whole(pair):
    a, b, pull, links = pair
    a.write("first", 1)
    a.write("second", 2)
    links[b.dir].tamper = True
    result = pull(b)
    assert result["error"] == sync_segments.DAMAGED
    assert b.notes() == [] and sync_state.peer(b.dir, a.device)["cursor"] == 0


def test_the_other_computer_offline_changes_nothing_and_says_so(pair):
    a, b, pull, links = pair
    a.write("first", 1)
    links[b.dir].fail = ConnectionError("no route to host")
    result = pull(b)
    assert result["error"] == sync_pull.OFFLINE and result["synced_at"] is None
    assert b.notes() == []
    links[b.dir].fail = None
    assert pull(b)["error"] == "" and b.texts() == ["first"]


def test_a_long_log_comes_over_in_turns(pair, monkeypatch):
    a, b, pull, links = pair
    monkeypatch.setattr(sync_segments, "MAX_NOTES", 2)
    for minute in range(5):
        a.write(f"note {minute}", minute)
    result = pull(b)
    assert result["error"] == "" and result["applied"] == 5
    assert links[b.dir].fetches == 3 and len(b.notes()) == 5


def test_a_segment_from_this_computer_is_refused(pair):
    a, _, _, _ = pair
    a.write("mine", 1)
    segment = sync_segments.export_segment(a.session, a.device, 0, "someone")
    with pytest.raises(sync_segments.SegmentError):
        sync_segments.apply_segment(a.session, a.device, segment)


def test_the_routes_say_not_paired_and_serve_a_segment(client):
    assert client.get("/sync/status").json()["paired"] is False
    assert client.post("/sync/now").json()["error"] == sync_pull.NOT_PAIRED
    client.post("/entries", json={"content": "Ship this one"})
    segment = client.get("/sync/segment", params={"since": 0, "peer": "abcdefabcdef"}).json()
    assert [n["content"] for n in segment["notes"]] == ["Ship this one"]
    assert segment["digest"] == sync_segments.digest(segment["notes"])
