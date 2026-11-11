"""Sync through a folder (WORLD_CLASS_PLAN B6 decision 14, row 36): two installs converge with no server.

Two data folders (`Notebook` from `tests/test_sync_segments.py`) stand for two computers; the shared folder is a
temp dir. The file carries the home-network segments, manifest and items, and is read through
`sync_pull.pull_from`, so these tests hold the folder to the same rules as the LAN tests. Times are stamped by
the test, never read off the clock.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.core import crypto, vault
from tessellate.core.database import Attachment, AuditLog, Document, Entry, EntryRevision
from tessellate.entry import folder_sync, manager, sync_pull, sync_segments
from tessellate.entry.manager_private import set_private
from tests.test_sync_segments import Link, Notebook

PASS = "correct horse battery"


def _at(minute: int) -> datetime:
    return datetime(2026, 11, 1, 12, minute)


@pytest.fixture()
def two(app_state, tmp_path, monkeypatch):
    """(notebook A, notebook B, folder). Home is the test's folder: a sync folder lives in home or on a removable drive."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
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


def _made_private(book: Notebook, entry: Entry, minute: int) -> None:
    vault.close()
    vault.create(book.session, "a-vault-passphrase")
    assert set_private(book.session, entry, True)
    book.stamp(entry, minute)


def _said(book: Notebook) -> str:
    book.session.expire_all()
    return json.dumps([[r.detail, r.payload] for r in book.session.scalars(select(AuditLog))], default=str)


def test_a_note_made_private_after_it_was_shared_is_withdrawn_from_the_other_computer(two):
    """PR 216 review: the folder leaves private notes out, so the other computer's plain copy stayed for good.
    A note shipped plain and then made private goes as a withheld marker, and the other computer's unchanged copy
    goes with its History and the words its log kept."""
    a, b, folder = two
    secret = note(a, "The gate code is 7731", 1)
    settle(a, b, folder)
    edit(a, secret, "The gate code is 7731, then hash", 2)
    settle(a, b, folder)
    assert "The gate code is 7731" in history(b)
    _made_private(a, secret, 3)
    sync(a, folder)
    raw = "".join(p.read_text("utf-8") for p in folder.glob("*.json"))
    assert "7731" not in raw
    got = sync(b, folder)
    assert got["error"] == "" and texts(b) == []
    assert not [h for h in history(b) if "7731" in h]
    assert "7731" not in _said(b)
    settle(a, b, folder)  # the marker again, and A's own private note untouched by B's file
    a.session.expire_all()
    assert a.session.get(Entry, secret.id).is_private and texts(b) == []


def test_a_withdrawn_note_edited_on_the_other_computer_is_kept_there_and_says_so(two):
    a, b, folder = two
    secret = note(a, "Meet at the north door", 1)
    settle(a, b, folder)
    edit(b, find(b, "Meet at the north door"), "Meet at the north door, bring the key", 4)
    _made_private(a, secret, 5)
    sync(a, folder)
    got = sync(b, folder)
    assert texts(b) == ["Meet at the north door, bring the key"]
    assert got["conflicts"] == 1
    assert sync_segments.WITHHELD_KEPT in _said(b)
    again = sync(b, folder)  # said once, not at every sync
    assert again["conflicts"] == 0 and _said(b).count(sync_segments.WITHHELD_KEPT) == 1


def test_a_note_private_before_it_was_ever_shared_sends_no_marker(two):
    a, _b, folder = two
    secret = note(a, "Never shared", 1)
    _made_private(a, secret, 2)
    sync(a, folder)
    (file,) = folder.glob("*.json")
    sealed = json.loads(file.read_text("utf-8"))
    key = folder_sync._key(PASS, base64.b64decode(sealed["salt"]))  # noqa: SLF001  # the file's own key
    body = json.loads(crypto.decrypt(key, sealed["data"]))
    assert [n for s in body["segments"] for n in s["notes"]] == []


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


def test_the_notebooks_own_folder_is_refused(two):
    """A sync file inside the notebook's folder would travel with every copy of it (CodeQL path injection review)."""
    a, _b, _folder = two
    inside = a.dir / "sub"
    inside.mkdir(parents=True, exist_ok=True)
    for chosen in (a.dir, inside):
        with pytest.raises(folder_sync.SyncError, match="outside the notebook"):
            sync(a, chosen)


def test_a_folder_outside_home_and_removable_drives_is_refused(two, tmp_path, monkeypatch):
    """The route takes a path from a request (CodeQL path injection): home and the removable-drive mounts only, judged after links."""
    a, _b, folder = two
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    with pytest.raises(folder_sync.SyncError, match="home folder or on a removable drive"):
        sync(a, folder)
    (tmp_path / "elsewhere" / "link").symlink_to(folder)
    with pytest.raises(folder_sync.SyncError, match="home folder or on a removable drive"):
        sync(a, tmp_path / "elsewhere" / "link")


def _reseal(file, change) -> None:
    """Rewrite a peer's file as someone who holds the passphrase could: decrypt, change the body, seal again."""
    sealed = json.loads(file.read_text("utf-8"))
    key = folder_sync._key(PASS, base64.b64decode(sealed["salt"]))  # noqa: SLF001  # the file's own key
    body = json.loads(crypto.decrypt(key, sealed["data"]))
    change(body)
    sealed["data"] = crypto.encrypt(key, json.dumps(body))
    file.write_text(json.dumps(sealed), "utf-8")


def test_a_peer_file_whose_device_names_another_folder_is_unreadable(two):
    """A device name becomes a folder name here (`tessellate-sync-<device>-files`): one that is not the 12
    letters and digits sync_state makes is refused, so `../x` never walks out of the sync folder."""
    a, b, folder = two
    note(a, "Travels only under its own name", 1)
    sync(a, folder)
    (file,) = folder.glob("*.json")
    _reseal(file, lambda body: body.update(device="../../escape"))
    got = sync(b, folder)
    assert got["unreadable"] == 1 and texts(b) == []


def test_a_manifest_sid_with_a_separator_is_refused_before_anything_is_fetched():
    """A sid becomes a file name in a sync folder (folder_sync._blob_name): only `<letters/digits>:<id>` passes."""
    from tessellate.entry import sync_extras, sync_extras_apply
    from tessellate.entry.sync_segments import SegmentError

    def answer(sid: str) -> dict:
        lines = [{"kind": "file", "sid": sid, "hash": "h"}]
        return {"format": sync_extras.FORMAT, "device": "abcdefabcdef", "items": lines, "digest": sync_extras.digest(lines)}

    assert sync_extras_apply.checked(answer("abcdefabcdef:12"), "abcdefabcdef")
    for bad in ("x:/../../../tmp/y", "../x:1", "x:a/b", "x:..\\y", "nocolon"):
        with pytest.raises(SegmentError):
            sync_extras_apply.checked(answer(bad), "abcdefabcdef")


def test_a_blob_name_outside_the_files_folder_is_neither_read_nor_written(tmp_path):
    blobs = tmp_path / "shared" / "tessellate-sync-abcdefabcdef-files"
    blobs.mkdir(parents=True)
    (blobs / "x-").mkdir()  # the folder a crafted sid walks through, planted by whoever writes the shared folder
    key = b"k" * 32
    sealed = {"sha1": "", "data": crypto.encrypt(key, base64.b64encode(b"outside").decode("ascii"))}
    (tmp_path / "shared" / "outside.bin").write_text(json.dumps(sealed), "utf-8")
    link = folder_sync.FolderLink({"device": "abcdefabcdef", "segments": [{"upto": 0}], "manifest": {}, "items": {}},
                                  blobs, key)
    assert link.file("x:/../../outside", "me") is None


def test_a_sibling_of_home_is_refused_and_home_itself_is_kept(tmp_path, monkeypatch):
    """The root is matched with its separator, so /home/user2 never passes for /home/user; home itself does."""
    home, sibling = tmp_path / "user", tmp_path / "user2"
    home.mkdir()
    sibling.mkdir()
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(folder_sync.SyncError, match="home folder or on a removable drive"):
        folder_sync._checked(str(sibling), PASS)  # noqa: SLF001  # the guard alone
    assert folder_sync._checked(str(home), PASS) == home.resolve()  # noqa: SLF001


def _copy_of(a: Notebook, b: Notebook) -> None:
    """B's data folder copied from A's: the same sync-state.json, so the same device id."""
    (b.dir / "sync-state.json").write_text((a.dir / "sync-state.json").read_text("utf-8"), "utf-8")


def test_a_peer_file_with_this_computers_own_device_is_refused_and_nothing_is_deleted(two):
    """PR 216 review: a data folder copied to a second computer shares its device id; a sync tool's conflict copy
    of the shared file (`tessellate-sync-<id> (conflicted copy).json`) must not be pulled as a peer."""
    a, b, folder = two
    note(a, "Written on the original", 1)
    sync(a, folder)
    (own,) = folder.glob("*.json")
    note(b, "Only on the copy", 2)
    _copy_of(a, b)
    (folder / own.name.replace(".json", " (conflicted copy).json")).write_text(own.read_text("utf-8"), "utf-8")
    own.unlink()
    got = sync(b, folder)
    assert got["unreadable"] == 1 and got["applied"] == 0
    assert got["error"] == sync_segments.SAME_ID
    assert texts(b) == ["Only on the copy"]


def test_a_peer_file_whose_name_is_not_its_device_is_refused(two):
    a, b, folder = two
    note(a, "Travels only under its own name", 1)
    sync(a, folder)
    (file,) = folder.glob("*.json")
    file.rename(folder / "tessellate-sync-000000000000.json")
    got = sync(b, folder)
    assert got["unreadable"] == 1 and got["peers"] == 0 and texts(b) == []


# --- documents and boards made private after sharing (INBOX 1783, PR 216 review) --------------------------------


def _shared_doc_and_board(a: Notebook, b: Notebook, folder) -> tuple[Document, Entry]:
    doc = Document(title="Boiler", content="Service code 5520.", updated_at=_at(1))
    board = Entry(content="Garden plan 5520", is_board=True, updated_at=_at(1))
    a.session.add_all([doc, board])
    a.session.commit()
    settle(a, b, folder)
    return doc, board


def _documents(book: Notebook) -> list[str]:
    book.session.expire_all()
    return [d.title for d in book.session.scalars(select(Document))]


def _boards(book: Notebook) -> list[str]:
    return [e.content for e in book.notes() if e.is_board]


def _make_private(book: Notebook, doc: Document, board: Entry, minute: int) -> None:
    vault.close()
    vault.create(book.session, "a-vault-passphrase")
    doc.is_private, doc.updated_at = True, _at(minute)
    assert set_private(book.session, board, True)
    book.stamp(board, minute)
    book.session.commit()


def test_a_document_and_a_board_made_private_after_sharing_are_withdrawn_from_the_other_computer(two):
    a, b, folder = two
    doc, board = _shared_doc_and_board(a, b, folder)
    assert _documents(b) == ["Boiler"] and _boards(b) == ["Garden plan 5520"]
    _make_private(a, doc, board, 3)
    sync(a, folder)
    raw = "".join(p.read_text("utf-8") for p in folder.glob("*.json"))
    assert "5520" not in raw
    body = _body(folder, a)
    assert body["items"]["document"][f"{a.device}:{doc.id}"]["withheld"] is True
    got = sync(b, folder)
    assert got["error"] == "" and _documents(b) == [] and _boards(b) == []
    assert "5520" not in _said(b)
    again = sync(b, folder)  # the marker is read again and does nothing more
    assert again["applied"] == again["conflicts"] == 0
    a.session.expire_all()
    assert a.session.get(Document, doc.id).is_private and a.session.get(Entry, board.id).is_private


def test_a_withdrawn_document_changed_on_the_other_computer_is_kept_there_and_says_so(two):
    a, b, folder = two
    doc, board = _shared_doc_and_board(a, b, folder)
    b.session.expire_all()
    mine = b.session.scalars(select(Document)).one()
    manager.log_action(b.session, "edited", "document", mine.id, "edited by hand")
    mine.content, mine.updated_at = "Service code 5520, plus my notes", _at(4)
    b.session.commit()
    _make_private(a, doc, board, 5)
    sync(a, folder)
    got = sync(b, folder)
    assert _documents(b) == ["Boiler"] and _boards(b) == []
    assert got["conflicts"] == 1
    assert _said(b).count(sync_segments.WITHHELD_KEPT) == 1
    again = sync(b, folder)
    assert again["conflicts"] == 0 and _said(b).count(sync_segments.WITHHELD_KEPT) == 1


def test_a_document_private_before_it_was_ever_shared_sends_no_marker(two):
    a, _b, folder = two
    vault.close()
    vault.set_key(crypto.new_dek())
    a.session.add(Document(title="Safe", content="The code is 4412", is_private=True, updated_at=_at(1)))
    a.session.commit()
    sync(a, folder)
    sync(a, folder)
    assert _body(folder, a)["items"]["document"] == {}


# --- two copies of one notebook writing the one same-named file (INBOX 1783) --------------------------------------


def _body(folder, book: Notebook) -> dict:
    sealed = json.loads((folder / f"tessellate-sync-{book.device}.json").read_text("utf-8"))
    return json.loads(crypto.decrypt(folder_sync._key(PASS, base64.b64decode(sealed["salt"])), sealed["data"]))  # noqa: SLF001


def _copy_state(a: Notebook, b: Notebook) -> None:
    """B's data folder copied from A's, folder_sync_state.json included."""
    _copy_of(a, b)
    (b.dir / folder_sync.STATE_FILE).write_text((a.dir / folder_sync.STATE_FILE).read_text("utf-8"), "utf-8")


def test_one_computer_syncing_again_and_again_never_trips_the_check(two):
    a, _b, folder = two
    note(a, "Alone", 1)
    for _ in range(3):
        assert sync(a, folder)["error"] == ""


def test_a_second_copy_writing_the_same_named_file_is_found_and_nothing_is_changed(two):
    a, b, folder = two
    note(a, "Written on the original", 1)
    sync(a, folder)
    _copy_state(a, b)  # the folder was copied to a second computer after the first sync
    note(a, "Later on the original", 2)
    sync(a, folder)  # the original writes the file again, with a token the copy did not write
    own = folder / f"tessellate-sync-{a.device}.json"
    before = own.read_bytes()
    note(b, "Only on the copy", 3)
    blobs = {p.name for p in folder.rglob("*")}
    got = sync(b, folder)
    assert got["error"] == sync_segments.SAME_ID and got["applied"] == got["conflicts"] == got["shared"] == 0
    assert own.read_bytes() == before and {p.name for p in folder.rglob("*")} == blobs
    assert texts(b) == ["Only on the copy"]
    assert sync(b, folder)["error"] == sync_segments.SAME_ID  # and the next press says it again


def test_a_copy_made_before_any_sync_is_found_too(two):
    a, b, folder = two
    _copy_of(a, b)
    note(a, "Original", 1)
    sync(a, folder)
    assert sync(b, folder)["error"] == sync_segments.SAME_ID


def test_a_file_from_before_tokens_existed_is_ours_and_is_rewritten(two):
    a, _b, folder = two
    sync(a, folder)
    own = folder / f"tessellate-sync-{a.device}.json"
    sealed = json.loads(own.read_text("utf-8"))
    key = folder_sync._key(PASS, base64.b64decode(sealed["salt"]))  # noqa: SLF001
    old = json.loads(crypto.decrypt(key, sealed["data"]))
    old.pop("token", None)
    sealed["data"] = crypto.encrypt(key, json.dumps(old))
    own.write_text(json.dumps(sealed), "utf-8")
    (a.dir / folder_sync.STATE_FILE).unlink()
    assert sync(a, folder)["error"] == ""
