"""Board, map, document and skill acts (L-chat-60): each write tool is reached by one sentence, drawn as a card that
waits for Confirm, run with no model and taken back by Undo. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from tessellate.ai import tools
from tessellate.core import deps
from tessellate.core.database import Document, Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch
from tessellate.entry import manager

from tests.test_parity_acts_1110 import card_of, confirm, stream, undo
from tests.test_library_acts_1114 import _fixed_now  # noqa: F401  (autouse clock)


def _run(client, sentence: str) -> tuple[dict, dict]:
    card = card_of(stream(client, sentence))
    return card, confirm(client, card)


def _sketches(session) -> list[str]:
    """Each drawing's data, a path's numbers read as numbers (a move and its Undo write 100.0 for 100)."""
    session.expire_all()
    return [re.sub(r"(\d+)\.0\b", r"\1", s.data) for s in session.scalars(select(WhiteboardSketch))]


def test_a_shape_is_drawn_after_confirm_and_taken_off_by_undo(client, session):
    card = card_of(stream(client, "draw a diamond that says Decide on the whiteboard"))
    assert card["steps"][0]["name"] == "add_board_shape" and card["steps"][0]["arguments"]["shape"] == "diamond"
    assert not _sketches(session), "nothing is drawn before Confirm"
    done = confirm(client, card)
    assert any('"label": "Decide"' in d for d in _sketches(session))
    undo(client, done)
    assert not _sketches(session)


def test_a_frame_is_drawn_and_taken_off(client, session):
    _, done = _run(client, "draw a frame called Q4 on the whiteboard")
    session.expire_all()
    assert [o.kind for o in session.scalars(select(WhiteboardObject))] == ["frame"]
    undo(client, done)
    session.expire_all()
    assert not list(session.scalars(select(WhiteboardObject)))


def test_a_library_item_is_placed_by_name_and_taken_off(client, session):
    card, done = _run(client, "put a decision symbol from the library on the whiteboard")
    assert card["steps"][0]["name"] == "place_library_item"
    assert _sketches(session) or list(session.scalars(select(WhiteboardObject)))
    undo(client, done)
    session.expire_all()
    assert not _sketches(session) and not list(session.scalars(select(WhiteboardObject)))


def test_an_unknown_library_item_says_so_and_draws_no_card(client):
    out = stream(client, "put a zzzqx from the library on the whiteboard")
    assert not out.get("act") and "nothing called" in out["text"]


def test_two_cards_are_connected_and_the_link_comes_off_with_undo(client, session):
    manager.create_entry(session, "# Boiler service\n\nDue in March.")
    manager.create_entry(session, "# Gym log\n\nSquats.")
    session.commit()
    for sentence in ("put the boiler service note on the whiteboard", "put the gym log note on the whiteboard"):
        confirm(client, card_of(stream(client, sentence)))
    card, done = _run(client, "connect the boiler card to the gym card on the whiteboard")
    assert card["steps"][0]["name"] == "add_whiteboard_link"
    assert len(_sketches(session)) == 1
    assert done["undo"][0]["name"] == "drop_board_link"
    undo(client, done)
    assert not _sketches(session) and len(list(session.scalars(select(WhiteboardNode)))) == 2


def test_move_reword_and_remove_an_item_each_with_its_own_undo(client, session):
    confirm(client, card_of(stream(client, "draw a rectangle that says Launch on the whiteboard")))
    before = _sketches(session)
    _, moved = _run(client, "move the Launch shape on the whiteboard to the right")
    assert _sketches(session) != before
    undo(client, moved)
    assert _sketches(session) == before
    _, worded = _run(client, "change the Launch shape on the whiteboard to say Ship it")
    assert '"label": "Ship it"' in _sketches(session)[0]
    undo(client, worded)
    assert '"label": "Launch"' in _sketches(session)[0]
    _, gone = _run(client, "take the Launch shape off the whiteboard")
    assert not _sketches(session) and gone["undo"][0]["name"] == "restore_board_item"
    undo(client, gone)
    assert '"label": "Launch"' in _sketches(session)[0]


def test_an_item_that_is_not_on_the_board_is_said_not_drawn(client):
    out = stream(client, "take the Zebra shape off the whiteboard")
    assert not out.get("act") and "no item on the whiteboard called" in out["text"]


def test_a_card_cannot_be_reworded(client, session):
    manager.create_entry(session, "# Boiler service\n\nDue in March.")
    session.commit()
    confirm(client, card_of(stream(client, "put the boiler service note on the whiteboard")))
    out = stream(client, "change the boiler service card on the whiteboard to say Ship it")
    assert not out.get("act") and "change the note itself" in out["text"]


def _map(session) -> dict:
    return tools.execute_tool(session, "create_mindmap", {"title": "Trips", "root_text": "Paris"})


def test_a_node_is_added_under_a_named_parent_and_undo_takes_it_off(client, session):
    made = _map(session)
    card, done = _run(client, "add the node Beach under Paris on the Trips mind map")
    assert card["steps"][0]["arguments"]["parent_id"] == made["root_id"]
    session.expire_all()
    nodes = {o.id: o for o in session.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == made["board_id"]))}
    assert len(nodes) == 2
    undo(client, done)
    session.expire_all()
    assert len(list(session.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == made["board_id"])))) == 1


def test_two_nodes_are_cross_linked_and_unlinked(client, session):
    made = _map(session)
    tools.execute_tool(session, "add_map_node", {"board_id": made["board_id"], "text": "Rome", "parent_id": made["root_id"]})
    card, done = _run(client, "link Paris to Rome on the Trips mind map")
    assert card["steps"][0]["name"] == "link_map_nodes" and len(_sketches(session)) == 1
    undo(client, done)
    assert not _sketches(session)


def test_a_map_that_does_not_exist_is_said(client):
    out = stream(client, "add the node Beach to the Nowhere mind map")
    assert not out.get("act") and "no mind map called" in out["text"]


def test_a_tree_of_new_notes_is_drawn_and_undo_bins_them(client, session):
    _, done = _run(client, "draw a diagram of Trips with Paris, Rome and Oslo")
    session.expire_all()
    assert len(list(session.scalars(select(WhiteboardNode)))) == 4
    titles = {e.content.splitlines()[0] for e in session.scalars(select(Entry)) if e.deleted_at is None}
    assert {"Trips", "Paris", "Rome", "Oslo"} <= {t.lstrip("# ") for t in titles}
    undo(client, done)
    session.expire_all()
    assert not list(session.scalars(select(WhiteboardNode)))
    assert not [e for e in session.scalars(select(Entry)) if e.deleted_at is None]


def test_a_document_is_written_with_its_body_and_binned_by_undo(client, session):
    card, done = _run(client, "write a document called Harbor report: Findings for the harbor.")
    assert card["steps"][0]["arguments"] == {"title": "Harbor report", "content": "Findings for the harbor"}
    session.expire_all()
    assert [d.title for d in session.scalars(select(Document))] == ["Harbor report"]
    undo(client, done)
    session.expire_all()
    assert all(d.deleted_at is not None for d in session.scalars(select(Document)))


def test_a_document_with_no_text_is_still_the_needs_a_model_line(client):
    out = stream(client, "write a document called Harbor report")
    assert not out.get("act") and "needs a model" in out["text"]


def test_a_skill_is_saved_and_undo_deletes_it(client):
    card, done = _run(client, "save a skill called Weekly tidy that tidies my notes")
    assert card["steps"][0]["name"] == "save_skill"
    assert [s["name"] for s in deps.get_config().get_preference("skills", [])] == ["Weekly tidy"]
    undo(client, done)
    assert deps.get_config().get_preference("skills", []) == []


def test_checking_what_it_learned_is_a_card_and_runs_with_no_model(client):
    card, done = _run(client, "check what you have learned")
    assert card["steps"][0]["name"] == "check_learned" and done["ok"]
    assert done["undo"][0]["name"] == "undo_learned_check"


@pytest.mark.parametrize("sentence", [
    "link the gym note to the running note", "move the gym note to Work", "delete the boiler note", "write a report", "write a document called Harbor report",
    "draw a graph", "add a reminder to the board meeting", "put the boiler note on the whiteboard and call me Sam",
])
def test_other_sentences_are_not_board_acts(sentence):
    from tessellate.ai import board_acts

    assert board_acts.read(sentence) is None


def test_the_registrys_board_intents_match_the_board_acts_intents():
    """The Guide splits acts into board and other lists by `act_registry._BOARD_INTENTS`; a board intent
    added in `board_acts.INTENTS` and not there would land in the wrong list."""
    from tessellate.ai import act_registry, board_acts

    assert act_registry._BOARD_INTENTS == board_acts.INTENTS  # noqa: SLF001
