"""L-whiteboard-12: a frame can be bound to a note property
(`binds: {property, value}`). A card dropped inside it writes that value to
its note ("a kanban that edits your notebook"), and the board's bind sync
moves a card whose note now holds another bound frame's value into that frame.
One field per frame."""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _note(client, text="# Ship the release\nWrite the notes."):
    out = client.post("/entries", json={"content": text})
    assert out.status_code in (200, 201), out.text
    return out.json()["id"]


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Kanban", "type": "board"}).json()["id"]


def _frame(client, bid, title, x, binds):
    body = {"kind": "frame", "data": {"content": title, "binds": binds}, "board_id": bid, "x": x, "y": 0, "z": 0, "width": 300, "height": 400}
    out = client.post("/whiteboard/objects", json=body)
    assert out.status_code in (200, 201), out.text
    return out.json()


def _props(client, eid):
    return client.get(f"/entries/{eid}/properties").json()["properties"]


def _move(client, node, x, y):
    out = client.put(f"/whiteboard/nodes/{node['id']}", json={"entry_id": node["entry_id"], "board_id": node["board_id"], "x": x, "y": y})
    assert out.status_code == 200, out.text
    return out.json()


def test_a_frame_keeps_its_binding_and_refuses_a_bad_name(client):
    bid = _board(client)
    frame = _frame(client, bid, "Done", 0, {"property": "status", "value": "Done"})
    assert frame["data"]["binds"] == {"property": "status", "value": "Done"}
    bad = {"kind": "frame", "data": {"content": "X", "binds": {"property": "a:b", "value": "x"}}, "board_id": bid, "x": 0, "y": 0, "width": 100, "height": 100}
    out = client.post("/whiteboard/objects", json=bad)
    assert out.status_code == 422


def test_a_card_dropped_in_a_bound_frame_writes_the_value_to_its_note(client):
    bid = _board(client)
    _frame(client, bid, "Doing", 0, {"property": "status", "value": "Doing"})
    _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    assert "status" not in _props(client, eid)
    _move(client, node, 450, 50)
    assert _props(client, eid)["status"] == ["Done"]
    _move(client, node, 20, 50)
    assert _props(client, eid)["status"] == ["Doing"]
    body = client.get(f"/entries/{eid}").json()["content"]
    assert "Write the notes." in body


def test_a_card_outside_every_bound_frame_leaves_its_note_alone(client):
    bid = _board(client)
    _frame(client, bid, "Done", 0, {"property": "status", "value": "Done"})
    _frame(client, bid, "Loose", 400, None)
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    _move(client, node, 450, 50)
    assert "status" not in _props(client, eid)


def test_the_sync_moves_a_card_whose_note_changed_into_its_frame(client):
    bid = _board(client)
    _frame(client, bid, "Doing", 0, {"property": "status", "value": "Doing"})
    done = _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 20, "y": 50}).json()
    _move(client, node, 20, 60)
    put = client.put(f"/entries/{eid}/properties", json={"properties": {"status": "Done"}})
    assert put.status_code == 200, put.text
    out = client.post(f"/whiteboard/boards/{bid}/binds/sync")
    assert out.status_code == 200, out.text
    assert out.json()["moved"] == [node["id"]]
    state = client.get(f"/whiteboard/?board_id={bid}").json()
    card = next(n for n in state["nodes"] if n["id"] == node["id"])
    assert done["x"] <= card["x"] <= done["x"] + done["width"] and done["y"] <= card["y"] <= done["y"] + done["height"]
    again = client.post(f"/whiteboard/boards/{bid}/binds/sync").json()
    assert again["moved"] == []


def test_the_board_syncs_on_open_and_the_frame_menu_binds():
    js = frontend_text("whiteboard.js")
    assert "/binds/sync" in js
    assert "Bind to a property" in js


PASSPHRASE = "test-passphrase"


def test_a_locked_private_note_is_never_written_or_moved(client, session):
    """Review 5899364438 item 1: a locked note reads as a placeholder; writing
    the binding wrote that placeholder over the note's sealed words."""
    from tessellate.core import vault
    from tessellate.core.database import Entry

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    bid = _board(client)
    _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client, "# Secret plan\nstatus: Doing\n\nThe words.")
    made_private = client.post(f"/entries/{eid}/privacy", json={"private": True})
    assert made_private.status_code == 200
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    vault.close()
    session.expire_all()
    sealed = session.get(Entry, eid).content
    _move(client, node, 450, 50)
    synced = client.post(f"/whiteboard/boards/{bid}/binds/sync").json()
    assert synced["moved"] == []
    session.expire_all()
    assert session.get(Entry, eid).content == sealed
    vault.open_with(session, PASSPHRASE)
    opened = client.get(f"/entries/{eid}").json()
    assert "The words." in opened["content"]
    vault.close()


def test_a_note_edited_meanwhile_keeps_its_edit_and_the_save_goes_on(client, monkeypatch):
    """Item 2: the write names the version it read, so an edit landing between
    the read and the write is refused (kept), and the save carries on."""
    from tessellate.api import routes_entries, wb_binds

    bid = _board(client)
    _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    real = routes_entries.update_entry

    def edited_meanwhile(entry_id, body, **kw):
        assert body.base_hash, "the binding write must name the version it read"
        real(entry_id, routes_entries.EntryUpdate(content="# Ship the release\nRewritten elsewhere."), response=kw["response"], session=kw["session"], if_match=None)
        return real(entry_id, body, **kw)

    monkeypatch.setattr(routes_entries, "update_entry", edited_meanwhile)
    moved = _move(client, node, 450, 50)
    assert moved["x"] == 450
    monkeypatch.setattr(routes_entries, "update_entry", real)
    kept = client.get(f"/entries/{eid}").json()
    assert "Rewritten elsewhere." in kept["content"]
    assert "status" not in _props(client, eid)
    assert wb_binds.write_binding  # the bulk save takes the same path


def test_a_binding_must_be_a_property_name_and_one_line(client):
    """Item 3: one line, a property-name pattern, and not title, tags or id."""
    bid = _board(client)
    for binds in ({"property": "title", "value": "x"}, {"property": "Tags", "value": "x"}, {"property": "1st", "value": "x"},
                  {"property": "status", "value": "two\nlines"}, {"property": "status", "value": "cr\rline"}, {"property": "a\nb", "value": "x"}):
        body = {"kind": "frame", "data": {"content": "X", "binds": binds}, "board_id": bid, "x": 0, "y": 0, "width": 100, "height": 100}
        refused = client.post("/whiteboard/objects", json=body)
        assert refused.status_code == 422, binds
    _frame(client, bid, "Ok", 0, {"property": "due date", "value": "Friday"})


def test_the_sync_loads_every_note_in_one_call():
    """Item 5: the cards' notes come in one query, not one per card."""
    src = (ROOT / "src" / "tessellate" / "api" / "wb_binds.py").read_text(encoding="utf-8")
    body = src[src.index("def sync_board_binds"):]
    assert "whiteboard_repo.entries(" in body and "whiteboard_repo.entry(" not in body
