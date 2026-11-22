"""Documents, boards and attached files between paired notebooks (WORLD_CLASS_PLAN B6, decision 13).

Two data folders pull from each other through `sync_pull.pull` over the
fake transport of `tests/test_sync_segments.py` (everything through JSON,
nothing shared). Times are stamped by the test, never read off the clock.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.core import crypto, vault
from tessellate.core.database import (
    Attachment,
    Document,
    DocumentLink,
    DocumentRevision,
    Entry,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
)
from tessellate.entry import sync_extras, sync_keys, sync_pull
from tests.test_sync_segments import Link, Notebook


def _at(minute: int) -> datetime:
    return datetime(2026, 11, 1, 12, minute)


@pytest.fixture()
def pair(app_state, tmp_path, monkeypatch):
    a, b = Notebook(tmp_path, "a"), Notebook(tmp_path, "b")
    links = {a.dir: Link(b), b.dir: Link(a)}
    current = {}
    monkeypatch.setattr(sync_pull, "_transport", lambda: current.get("link"))

    def pull(into: Notebook) -> dict:
        current["link"] = links[into.dir]
        into.session.expire_all()
        return sync_pull.pull(into.session, into.dir)

    yield a, b, pull
    for book in (a, b):
        book.session.close()
    vault.close()


def _documents(book: Notebook) -> list[Document]:
    book.session.expire_all()
    return list(book.session.scalars(select(Document).order_by(Document.id)))


def _document(book: Notebook, title: str, content: str, minute: int) -> Document:
    doc = Document(title=title, content=content, updated_at=_at(minute))
    book.session.add(doc)
    book.session.commit()
    return doc


def test_a_document_and_its_linked_note_reach_the_other_and_a_second_pull_changes_nothing(pair):
    a, b, pull = pair
    note = a.write("Boiler service notes", 1)
    doc = _document(a, "Boiler", "# Boiler\n\nService in March.", 2)
    a.session.add(DocumentLink(document_id=doc.id, entry_id=note.id))
    a.session.commit()
    first = pull(b)
    assert first["error"] == "" and first["applied"] == 2  # the note, then the document
    [copy] = _documents(b)
    assert (copy.title, copy.content) == ("Boiler", "# Boiler\n\nService in March.")
    linked = b.session.scalars(select(DocumentLink.entry_id).where(DocumentLink.document_id == copy.id)).all()
    assert linked == [b.notes()[0].id]
    assert pull(b)["applied"] == 0 and len(_documents(b)) == 1
    # And it is not shipped back as new: A already has it.
    assert pull(a)["applied"] == 0 and len(_documents(a)) == 1


def test_a_document_edited_on_both_the_later_wins_and_the_other_words_stay_in_history(pair):
    a, b, pull = pair
    doc = _document(a, "Plan", "first draft", 1)
    pull(b)
    [theirs] = _documents(b)
    doc.content, doc.updated_at = "A's second draft", _at(3)
    a.session.commit()
    theirs.content, theirs.updated_at = "B's second draft", _at(5)
    b.session.commit()
    assert pull(b)["conflicts"] == 1 and _documents(b)[0].content == "B's second draft"
    assert pull(a)["applied"] == 1 and _documents(a)[0].content == "B's second draft"
    for book in (a, b):
        kept = book.session.scalars(select(DocumentRevision.content)).all()
        assert "A's second draft" in kept, book.dir.name
    # An edit made only on B since then goes to A whatever the clocks say.
    theirs = _documents(b)[0]
    theirs.content, theirs.updated_at = "B's third draft", _at(4)
    b.session.commit()
    assert pull(a)["applied"] == 1 and _documents(a)[0].content == "B's third draft"


def test_a_sub_page_keeps_its_parent_across_the_pull_whichever_arrives_first(pair):
    a, b, pull = pair
    child = _document(a, "Child", "c", 2)  # the lower id: it is written before its parent on the other side
    parent = _document(a, "Parent", "p", 1)
    child.parent_id = parent.id
    a.session.commit()
    assert pull(b)["error"] == ""
    on_b = {d.title: d for d in _documents(b)}
    assert on_b["Child"].parent_id == on_b["Parent"].id and on_b["Parent"].parent_id is None
    # A sub-page moved back to the top level on A follows.
    child.parent_id, child.updated_at = None, _at(5)
    a.session.commit()
    pull(b)
    assert {d.title: d.parent_id for d in _documents(b)}["Child"] is None
    # A parent that is not here (never shipped, or a cycle) leaves the page at the top level, never a bad id.
    state = sync_extras.document_state(a.session, child, sync_extras.names_for(a.session, a.dir, a.device))
    assert "parent" not in state


def _board(book: Notebook, note: Entry, minute: int) -> Entry:
    board = Entry(content="Garden plan", is_board=True, updated_at=_at(minute))
    book.session.add(board)
    book.session.flush()
    card = WhiteboardNode(board_id=board.id, entry_id=note.id, x=10, y=20, updated_at=_at(minute))
    shape = WhiteboardObject(board_id=board.id, kind="rect", data=json.dumps({"w": 40}), updated_at=_at(minute))
    book.session.add_all([card, shape])
    book.session.flush()
    line = WhiteboardSketch(board_id=board.id, data=json.dumps({"sourceId": card.id, "sourceKind": "node",
                            "targetId": shape.id, "targetKind": "object"}), updated_at=_at(minute))
    book.session.add(line)
    book.session.commit()
    return board


def _canvas(book: Notebook) -> tuple[Entry, list, list, list]:
    book.session.expire_all()
    [board] = book.session.scalars(select(Entry).where(Entry.is_board.is_(True))).all()
    rows = [list(book.session.scalars(select(m).where(m.board_id == board.id).order_by(m.id)))
            for _, m in sync_extras.CANVAS]
    # Spelled out so a reader (and CodeQL) sees the four-way unpack the tests do (one row list per CANVAS kind).
    return board, rows[0], rows[1], rows[2]


def test_a_board_comes_over_with_its_cards_shapes_and_connector_joined_to_the_new_rows(pair):
    a, b, pull = pair
    note = a.write("Tulips by the fence", 1)
    _board(a, note, 2)
    assert pull(b)["error"] == ""
    board, nodes, sketches, objects = _canvas(b)
    assert board.content == "Garden plan" and [n.entry_id for n in nodes] == [b.notes()[0].id]
    assert (nodes[0].x, nodes[0].y) == (10, 20) and json.loads(objects[0].data) == {"w": 40}
    joined = json.loads(sketches[0].data)
    assert (joined["sourceId"], joined["targetId"]) == (nodes[0].id, objects[0].id)
    assert pull(b)["applied"] == 0 and pull(a)["applied"] == 0


def test_a_card_moved_on_one_and_a_drawing_removed_on_the_other_both_arrive(pair):
    a, b, pull = pair
    note = a.write("Tulips", 1)
    _board(a, note, 2)
    pull(b)
    pull(a)
    _, nodes, _, _ = _canvas(b)
    nodes[0].x, nodes[0].updated_at = 300, _at(6)
    b.session.commit()
    assert pull(a)["applied"] == 1 and _canvas(a)[1][0].x == 300
    pull(b)
    # A rubs out the connector: no time moves, the three-way hash still carries it.
    _, _, sketches, _ = _canvas(a)
    a.session.delete(sketches[0])
    a.session.commit()
    assert pull(b)["applied"] == 1 and _canvas(b)[2] == []
    assert pull(a)["applied"] == 0 and _canvas(a)[2] == []


def _attach(book: Notebook, note: Entry, name: str, data: bytes) -> Attachment:
    uploads = book.dir / "uploads"
    uploads.mkdir(exist_ok=True)
    stored = f"{name}.bin"
    (uploads / stored).write_bytes(data)
    att = Attachment(entry_id=note.id, filename=name, stored_name=stored, mime="image/png", size=len(data))
    book.session.add(att)
    book.session.commit()
    return att


def test_an_attached_file_comes_over_byte_for_byte_and_a_removal_follows_both_ways(pair):
    a, b, pull = pair
    note = a.write("Receipt", 1)
    _attach(a, note, "receipt.png", b"\x89PNG fake bytes")
    assert pull(b)["error"] == ""
    [copy] = b.session.scalars(select(Attachment)).all()
    assert copy.entry_id == b.notes()[0].id and copy.filename == "receipt.png"
    assert (b.dir / "uploads" / copy.stored_name).read_bytes() == b"\x89PNG fake bytes"
    assert pull(b)["applied"] == 0 and pull(a)["applied"] == 0
    # Removed on B (where it arrived): A removes its own at its next pull.
    (b.dir / "uploads" / copy.stored_name).unlink()
    b.session.delete(copy)
    b.session.commit()
    pull(a)
    a.session.expire_all()
    assert a.session.scalars(select(Attachment)).all() == []
    # A file added on B and removed there later is removed on A too.
    second = _attach(b, b.notes()[0], "second.png", b"two")
    pull(a)
    assert [x.filename for x in a.session.scalars(select(Attachment))] == ["second.png"]
    b.session.delete(second)
    b.session.commit()
    pull(a)
    a.session.expire_all()
    assert a.session.scalars(select(Attachment)).all() == []


def test_a_file_changed_on_the_way_is_refused(pair, monkeypatch):
    a, b, pull = pair
    note = a.write("Receipt", 1)
    _attach(a, note, "receipt.png", b"real bytes")
    link_file = Link.file
    monkeypatch.setattr(Link, "file", lambda self, sid, me: b"other bytes")
    result = pull(b)
    assert result["error"] != "" and b.session.scalars(select(Attachment)).all() == []
    monkeypatch.setattr(Link, "file", link_file)
    assert pull(b)["error"] == "" and len(b.session.scalars(select(Attachment)).all()) == 1


def test_a_private_document_opens_on_the_other_with_both_keys_and_waits_without(pair, monkeypatch):
    a, b, pull = pair
    vault.close()
    a_key, b_key = crypto.new_dek(), crypto.new_dek()
    vault.set_key(a_key)
    doc = Document(title="Safe", content="The code is 4412", is_private=True, updated_at=_at(1))
    a.session.add(doc)
    a.session.commit()
    stored = sync_extras.raw(a.session, Document, doc.id)
    assert crypto.is_encrypted(stored["content"]) and "4412" not in json.dumps(Link(a).items("document", [f"{a.device}:{doc.id}"], b.device))
    vault.set_key(b_key)
    monkeypatch.setattr(sync_keys, "keys", lambda data_dir: None)
    assert pull(b)["applied"] == 0 and _documents(b) == []  # no keys: it waits
    monkeypatch.setattr(sync_keys, "keys", lambda data_dir: (a_key, b_key))
    assert pull(b)["applied"] == 1
    [copy] = _documents(b)
    assert copy.is_private and (copy.title, copy.content) == ("Safe", "The code is 4412")
    assert crypto.decrypt(b_key, sync_extras.raw(b.session, Document, copy.id)["content"]) == "The code is 4412"
    assert pull(b)["applied"] == 0


def test_a_private_board_opens_on_the_other_with_both_keys(pair, monkeypatch):
    a, b, pull = pair
    vault.close()
    a_key, b_key = crypto.new_dek(), crypto.new_dek()
    vault.set_key(a_key)
    note = a.write("Secret garden", 1)
    board = _board(a, note, 2)
    board.is_private = True
    a.session.commit()
    for row in a.session.scalars(select(WhiteboardObject)):
        row.data = json.dumps({"w": 41})
    a.session.commit()
    assert crypto.is_encrypted(sync_extras.raw(a.session, WhiteboardObject, 1)["data"])
    vault.set_key(b_key)
    monkeypatch.setattr(sync_keys, "keys", lambda data_dir: (a_key, b_key))
    assert pull(b)["error"] == ""
    copy, nodes, sketches, objects = _canvas(b)
    assert copy.is_private and json.loads(objects[0].data) == {"w": 41}
    joined = json.loads(sketches[0].data)
    assert (joined["sourceId"], joined["targetId"]) == (nodes[0].id, objects[0].id)
    assert crypto.is_encrypted(sync_extras.raw(b.session, WhiteboardObject, objects[0].id)["data"])


def test_the_routes_serve_a_manifest_items_and_a_file(client, app_state):
    entry = client.post("/entries", json={"content": "Ship this one"}).json()
    created = client.post("/documents", json={"title": "Doc", "content": "Body"})
    assert created.status_code in (200, 201)
    manifest = client.get("/sync/manifest", params={"peer": "abcdefabcdef"}).json()
    kinds = sorted(x["kind"] for x in manifest["items"])
    assert kinds == ["document"] and manifest["digest"] == sync_extras.digest(manifest["items"])
    sid = manifest["items"][0]["sid"]
    [item] = client.get("/sync/items", params={"kind": "document", "sid": sid, "peer": "abcdefabcdef"}).json()["items"]
    assert (item["title"], item["content"]) == ("Doc", "Body") and entry["id"]
    missing = client.get("/sync/file", params={"sid": "nothing:1", "peer": "abcdefabcdef"})
    assert missing.status_code == 404


def test_a_kill_between_a_commit_and_the_page_flush_leaves_no_duplicates(pair, monkeypatch):
    from tessellate.entry import sync_extras_apply

    a, b, pull = pair
    note = a.write("Receipt", 1)
    _document(a, "Boiler", "service", 2)
    _attach(a, note, "receipt.png", b"bytes")
    monkeypatch.setattr(sync_extras_apply.Apply, "flush", lambda self: None)  # killed before the page-end write
    for _ in range(2):
        pull(b)
        pull(a)
    for book in (a, b):
        book.session.expire_all()
        assert len(_documents(book)) == 1, book.dir.name
        assert len(book.session.scalars(select(Attachment)).all()) == 1, book.dir.name


def test_the_upload_hash_cache_survives_threads_hammering_a_full_cache(tmp_path, monkeypatch):
    import threading

    monkeypatch.setattr(sync_extras, "_SHA1_CACHE_MAX", 8)
    files = []
    for n in range(40):
        path = tmp_path / f"f{n}"
        path.write_bytes(bytes([n]))
        files.append(path)
    errors: list[Exception] = []

    def hammer() -> None:
        try:
            for _ in range(200):
                for path in files:
                    sync_extras._file_sha1(path, path.name)  # noqa: SLF001
        except (RuntimeError, KeyError, StopIteration) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and len(sync_extras._SHA1_CACHE) <= 8  # noqa: SLF001
