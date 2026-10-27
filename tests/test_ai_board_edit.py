"""The assistant edits boards (FEAT-12; WHITEBOARD_PLAN decision 29).

Move, edit and delete ask the person first (`destructive`), each is one
event, and each returns the undo the run summary offers. A shape can be drawn
and the object library searched and placed from. Run against the handlers
and `execute_tool`, which is the path the confirm button takes; no model.
"""

from __future__ import annotations

import json

from tessellate.ai import tools
from tessellate.core.database import AuditLog, Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch

RECT = "M 10 20 L 110 20 L 110 80 L 10 80 Z"


def _events(session, entity):
    return session.query(AuditLog).filter(AuditLog.entity_type == entity).count()


def test_move_edit_and_delete_ask_first_and_drawing_does_not():
    for name in ("move_board_item", "edit_board_item", "delete_board_item"):
        assert tools.TOOLS[name].destructive, name
        assert name in tools.WRITE_TOOLS
    for name in ("add_board_shape", "place_library_item", "list_library"):
        assert not tools.TOOLS[name].destructive, name
    assert "Take shape #4 off the board" == tools.confirm_label("delete_board_item", {"kind": "shape", "item_id": 4})


def test_move_a_shape_and_undo_it(session):
    shape = WhiteboardSketch(data=json.dumps({"d": RECT, "shape": "rect"}))
    session.add(shape)
    session.commit()
    before = _events(session, "whiteboard_sketch")
    out = tools.execute_tool(session, "move_board_item", {"kind": "shape", "item_id": shape.id, "x": 300, "y": 400})
    assert "error" not in out, out
    session.refresh(shape)
    assert json.loads(shape.data)["d"].startswith("M 300 400")
    assert _events(session, "whiteboard_sketch") == before + 1
    undo = out["undo"]
    assert undo["tool"] == "move_board_item" and (undo["arguments"]["x"], undo["arguments"]["y"]) == (10, 20)
    tools.execute_tool(session, "move_board_item", undo["arguments"])
    session.refresh(shape)
    assert json.loads(shape.data)["d"].startswith("M 10 20")


def test_move_a_card_and_refuse_a_locked_one(session):
    entry = Entry(content="A note")
    session.add(entry)
    session.commit()
    card = WhiteboardNode(entry_id=entry.id, x=0, y=0)
    locked = WhiteboardNode(entry_id=entry.id, x=5, y=5, locked=True)
    session.add_all([card, locked])
    session.commit()
    out = tools.execute_tool(session, "move_board_item", {"kind": "card", "item_id": card.id, "x": 50, "y": 60})
    session.refresh(card)
    assert (card.x, card.y) == (50, 60), out
    refused = tools.execute_tool(session, "move_board_item", {"kind": "card", "item_id": locked.id, "x": 1, "y": 1})
    assert "locked" in refused["error"]


def test_edit_words_and_colours_with_an_undo(session):
    box = WhiteboardObject(kind="text", data=json.dumps({"content": "Risks", "color": "#000000"}), x=0, y=0, width=100, height=40)
    shape = WhiteboardSketch(data=json.dumps({"d": RECT, "shape": "rect", "label": "Old"}))
    session.add_all([box, shape])
    session.commit()
    out = tools.execute_tool(session, "edit_board_item", {"kind": "object", "item_id": box.id, "color": "cc3333", "fill": "#ffeeee"})
    session.refresh(box)
    data = json.loads(box.data)
    assert data["color"] == "#cc3333" and data["bg"] == "#ffeeee", out
    assert out["undo"]["arguments"]["color"] == "#000000"
    out = tools.execute_tool(session, "edit_board_item", {"kind": "shape", "item_id": shape.id, "text": "New words"})
    session.refresh(shape)
    assert json.loads(shape.data)["label"] == "New words"
    assert out["undo"]["arguments"]["text"] == "Old"
    bad = tools.execute_tool(session, "edit_board_item", {"kind": "shape", "item_id": shape.id, "color": "red; x"})
    assert "colour" in bad["error"]


def test_a_sticky_s_folded_corner_is_set_and_undone(session):
    """OPEN row 810: the assistant kept a sticky's fold but could not set it."""
    sticky = WhiteboardObject(kind="text", data=json.dumps({"content": "Idea", "sticky": True, "bg": "#fff3a0"}), x=0, y=0, width=120, height=120)
    plain = WhiteboardObject(kind="text", data=json.dumps({"content": "Plain"}), x=0, y=0, width=100, height=40)
    session.add_all([sticky, plain])
    session.commit()
    out = tools.execute_tool(session, "edit_board_item", {"kind": "object", "item_id": sticky.id, "fold": False})
    session.refresh(sticky)
    assert json.loads(sticky.data)["fold"] is False and "corner" in out["changed"], out
    assert out["undo"]["arguments"]["fold"] is True
    back = tools.execute_tool(session, "edit_board_item", out["undo"]["arguments"])
    session.refresh(sticky)
    assert json.loads(sticky.data)["fold"] is True, back
    refused = tools.execute_tool(session, "edit_board_item", {"kind": "object", "item_id": plain.id, "fold": True})
    assert "sticky" in refused["error"]


def test_a_card_and_a_connector_are_not_edited_here(session):
    entry = Entry(content="A note")
    session.add(entry)
    session.commit()
    card = WhiteboardNode(entry_id=entry.id, x=0, y=0)
    session.add(card)
    session.commit()
    link = WhiteboardSketch(data=json.dumps({"type": "link-straight", "sourceId": card.id, "targetId": card.id}))
    session.add(link)
    session.commit()
    assert "note" in tools.execute_tool(session, "edit_board_item", {"kind": "card", "item_id": card.id, "text": "x"})["error"]
    assert "connector" in tools.execute_tool(session, "move_board_item", {"kind": "shape", "item_id": link.id, "x": 1, "y": 1})["error"]


def test_delete_takes_its_connectors_and_the_undo_puts_both_back(session):
    a = WhiteboardSketch(data=json.dumps({"d": RECT, "shape": "rect"}))
    b = WhiteboardSketch(data=json.dumps({"d": RECT, "shape": "rect"}))
    session.add_all([a, b])
    session.commit()
    link = WhiteboardSketch(data=json.dumps({"type": "link-straight", "sourceId": a.id, "sourceKind": "sketch", "targetId": b.id, "targetKind": "sketch"}))
    session.add(link)
    session.commit()
    out = tools.execute_tool(session, "delete_board_item", {"kind": "shape", "item_id": a.id})
    assert "error" not in out, out
    assert session.get(WhiteboardSketch, a.id) is None and session.get(WhiteboardSketch, link.id) is None
    back = tools.execute_tool(session, "restore_board_item", out["undo"]["arguments"])
    assert "error" not in back, back
    links = [s for s in session.query(WhiteboardSketch).all() if json.loads(s.data).get("type") == "link-straight"]
    assert len(links) == 1 and json.loads(links[0].data)["sourceId"] == back["item_id"]


def test_draw_shapes_and_a_frame(session):
    out = tools.execute_tool(session, "add_board_shape", {"shape": "diamond", "x": 0, "y": 0, "width": 100, "height": 60, "text": "Approved?"})
    shape = session.get(WhiteboardSketch, out["item_id"])
    data = json.loads(shape.data)
    assert data["label"] == "Approved?" and data["shape"] == "diamond" and data["d"].startswith("M 50.0 0.0")
    assert out["undo"] == {"tool": "delete_board_item", "arguments": {"kind": "shape", "item_id": shape.id}}
    frame = tools.execute_tool(session, "add_board_shape", {"shape": "frame", "text": "Ideas"})
    assert session.get(WhiteboardObject, frame["item_id"]).kind == "frame"
    assert "shape is one of" in tools.execute_tool(session, "add_board_shape", {"shape": "star"})["error"]


def test_a_shape_the_assistant_draws_lands_on_top(session):
    """Strokes and cards stack in one order (WHITEBOARD_PLAN decision 43), so
    a shape drawn at a fixed z 2 went under a card at z 7."""
    session.add(WhiteboardObject(board_id=None, kind="text", data="{}", x=0, y=0, z=7, width=50, height=50))
    session.add(WhiteboardObject(board_id=None, kind="frame", data="{}", x=0, y=0, z=40, width=50, height=50))
    session.commit()
    out = tools.execute_tool(session, "add_board_shape", {"shape": "rect", "x": 0, "y": 0, "width": 10, "height": 10})
    assert session.get(WhiteboardSketch, out["item_id"]).z == 8


def test_read_whiteboard_names_the_shapes_with_words(session):
    shape = WhiteboardSketch(data=json.dumps({"d": RECT, "shape": "rect", "label": "Launch"}))
    stroke = WhiteboardSketch(data=json.dumps({"d": "M 0 0 L 5 5", "shape": "pen"}))
    session.add_all([shape, stroke])
    session.commit()
    out = tools.TOOLS["read_whiteboard"].handler(session, {})
    assert out["shapes"] == [{"shape_id": shape.id, "shape": "rect", "text": "Launch", "x": 10, "y": 20}]


def test_search_and_place_from_the_library(ai_client, session):
    found = tools.execute_tool(session, "list_library", {"query": "decision"})
    refs = [i["ref"] for i in found["items"]]
    assert any(r.startswith("builtin:flowchart/") for r in refs), found
    ref = next(r for r in refs if r.startswith("builtin:flowchart/"))
    out = tools.execute_tool(session, "place_library_item", {"ref": ref, "x": 200, "y": 200})
    assert "error" not in out, out
    assert out["sketch_ids"] or out["object_ids"]
    assert out["undo"]["tool"] in ("delete_board_item", "batch")
    assert "ref is one" in tools.execute_tool(session, "place_library_item", {"ref": "nonsense"})["error"]
