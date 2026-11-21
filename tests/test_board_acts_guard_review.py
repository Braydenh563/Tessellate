"""PR 230 review: `drop_board_link` and `drop_map_node` are runnable steps, so
a stale or hand-edited Undo could name any row. They take only what they say
(a link sketch, a map node), never on a private board, and a node goes with
its links and only when it has no children; a card on the board for a binned
note is not offered by name."""

from __future__ import annotations

import json

from tessellate.ai import board_acts
from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch
from tessellate.entry import manager


def _board(session):
    board = manager.create_entry(session, "# Plan map")
    session.commit()
    return board


def _sketch(session, board_id, data: dict) -> WhiteboardSketch:
    row = WhiteboardSketch(board_id=board_id, data=json.dumps(data))
    session.add(row)
    session.commit()
    return row


def _node(session, board_id, kind="topic", parent_id=None) -> WhiteboardObject:
    row = WhiteboardObject(board_id=board_id, kind=kind, data=json.dumps({"content": "Topic"}), x=0, y=0, z=1, parent_id=parent_id)
    session.add(row)
    session.commit()
    return row


def test_drop_board_link_refuses_a_shape(session):
    shape = _sketch(session, None, {"type": "rect", "label": "Launch"})
    out = board_acts.run_step(session, "drop_board_link", {"id": shape.id})
    assert "error" in out
    assert session.get(WhiteboardSketch, shape.id) is not None


def test_drop_board_link_takes_a_link(session):
    link = _sketch(session, None, {"type": "link-straight", "sourceId": 1, "targetId": 2})
    out = board_acts.run_step(session, "drop_board_link", {"id": link.id})
    assert "error" not in out
    session.expire_all()
    assert session.get(WhiteboardSketch, link.id) is None


def test_nothing_is_taken_off_a_private_board(session):
    board = _board(session)
    link = _sketch(session, board.id, {"type": "link-curved", "sourceId": 1, "targetId": 2})
    node = _node(session, board.id)
    #: Made private after its rows: a locked vault refuses a write to a private board's rows.
    board.is_private = True
    session.commit()
    assert "error" in board_acts.run_step(session, "drop_board_link", {"id": link.id})
    assert "error" in board_acts.run_step(session, "drop_map_node", {"id": node.id})
    session.expire_all()
    assert session.get(WhiteboardSketch, link.id) is not None and session.get(WhiteboardObject, node.id) is not None


def test_drop_map_node_refuses_a_frame_and_a_node_with_children(session):
    board = _board(session)
    frame = _node(session, board.id, kind="frame")
    parent = _node(session, board.id)
    _node(session, board.id, parent_id=parent.id)
    assert "error" in board_acts.run_step(session, "drop_map_node", {"id": frame.id})
    assert "error" in board_acts.run_step(session, "drop_map_node", {"id": parent.id})
    session.expire_all()
    assert session.get(WhiteboardObject, frame.id) is not None and session.get(WhiteboardObject, parent.id) is not None


def test_drop_map_node_takes_its_cross_links_with_it(session):
    board = _board(session)
    a, b = _node(session, board.id), _node(session, board.id)
    link = _sketch(session, board.id, {"type": "link-curved", "sourceId": a.id, "sourceKind": "object", "targetId": b.id, "targetKind": "object"})
    out = board_acts.run_step(session, "drop_map_node", {"id": a.id})
    assert "error" not in out
    session.expire_all()
    assert session.get(WhiteboardObject, a.id) is None and session.get(WhiteboardSketch, link.id) is None


def test_a_card_for_a_binned_note_is_not_offered(session):
    kept = manager.create_entry(session, "# Boiler service\n\nDue in March.")
    binned = manager.create_entry(session, "# Old gym log\n\nSquats.")
    session.commit()
    for entry in (kept, binned):
        session.add(WhiteboardNode(board_id=None, entry_id=entry.id, x=0, y=0))
    session.commit()
    manager.soft_delete_entry(session, binned)
    session.commit()
    words = [row[0] for row in board_acts._board_items(session, "card")]
    assert words == ["Boiler service"]
