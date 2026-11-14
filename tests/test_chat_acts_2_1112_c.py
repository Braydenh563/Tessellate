"""Document, skill, whiteboard and mind-map acts (L-chat-26), both ways: the composer draws a card and
nothing happens before Confirm; Undo puts it back; the model's tool parks for the same Confirm and
returns the same undo. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import act_registry, commands, tools
from tessellate.core import deps
from tessellate.core.database import Document, Entry, WhiteboardNode
from tessellate.entry import manager

from tests.test_parity_acts_1110 import card_of, confirm, stream, undo

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.api import chat_said, chat_turn, routes_chat, routes_insights
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn, routes_insights):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def notebook(session):
    manager.create_entry(session, "# Boiler service\n\nBook the engineer for March.", category_name="Life")
    session.add(Document(title="Harbor report", content="Findings for the harbor."))
    session.commit()
    deps.get_config().set_preference("skills", [{"name": "Weekly tidy", "prompt": "Tidy my notes.", "steps": []}])
    return session


def _docs(session):
    session.expire_all()
    return {d.title: d.content for d in session.scalars(select(Document))}


def test_delete_a_document_waits_then_undo_restores(client, notebook):
    out = stream(client, "delete the document Harbor report")
    card = card_of(out)
    assert [s["name"] for s in card["steps"]] == ["delete_document"]
    assert "Harbor report" in _docs(notebook)
    done = confirm(client, card)
    assert "Harbor report" not in _docs(notebook)
    undo(client, done)
    assert _docs(notebook)["Harbor report"] == "Findings for the harbor."


def test_delete_a_skill_waits_then_undo_restores(client, notebook):
    card = card_of(stream(client, "delete the Weekly tidy skill"))
    assert [s["name"] for s in card["steps"]] == ["delete_skill"]
    assert deps.get_config().get_preference("skills")
    done = confirm(client, card)
    assert not deps.get_config().get_preference("skills")
    undo(client, done)
    assert [s["name"] for s in deps.get_config().get_preference("skills")] == ["Weekly tidy"]


def test_a_builtin_skill_is_refused_with_no_card(client, notebook):
    from tessellate.ai import skills

    name = skills.builtins()[0]["name"]
    out = stream(client, f"delete the {name} skill")
    assert not out.get("act") or not [e for e in out["act"] if e.get("steps")]


def test_put_a_note_on_the_board_then_undo_removes_the_card(client, notebook):
    card = card_of(stream(client, "put the boiler note on the whiteboard"))
    assert [s["name"] for s in card["steps"]] == ["add_whiteboard_card"]
    assert not notebook.scalars(select(WhiteboardNode)).all()
    done = confirm(client, card)
    notebook.expire_all()
    assert notebook.scalars(select(WhiteboardNode)).all()
    undo(client, done)
    notebook.expire_all()
    assert not notebook.scalars(select(WhiteboardNode)).all()


def test_a_mind_map_from_a_note_then_undo_bins_the_map(client, notebook):
    before = len(notebook.scalars(select(Entry)).all())
    card = card_of(stream(client, "make a mind map from the boiler note"))
    assert [s["name"] for s in card["steps"]] == ["map_from_note"]
    assert len(notebook.scalars(select(Entry)).all()) == before
    done = confirm(client, card)
    notebook.expire_all()
    assert len(notebook.scalars(select(Entry)).all()) > before
    undo(client, done)
    notebook.expire_all()
    assert len([e for e in notebook.scalars(select(Entry)) if not e.deleted_at]) == before


def test_a_mind_map_by_title_is_a_card(client, notebook):
    card = card_of(stream(client, "make a mind map about sourdough"))
    assert card["steps"][0]["name"] == "create_mindmap"


# --- the model's path: the same acts, the same Confirm ------------------------------------


@pytest.mark.parametrize("tool", ["delete_document", "delete_skill", "add_whiteboard_card", "map_from_note", "create_mindmap"])
def test_the_models_tool_parks_for_the_same_confirm(tool):
    assert tools.needs_confirm(tool, {}) is True


def test_every_act_maps_to_the_tool_the_model_has():
    for intent, tool in (("delete_document", "delete_document"), ("delete_skill", "delete_skill"), ("board_card", "add_whiteboard_card"), ("make_map", "map_from_note")):
        assert act_registry.ACT_TOOLS[intent] == tool and act_registry.ACTS[intent].confirm and tool in tools.TOOLS


def test_the_models_delete_document_returns_the_same_undo(notebook):
    doc_id = notebook.scalars(select(Document)).first().id
    result = tools.execute_tool(notebook, "delete_document", {"document_id": doc_id})
    #: The delete moved to the bin (review 5883496750), so its Undo restores the same row, not a new document.
    assert result["undo"]["tool"] == "restore_document"
    assert commands.RUNNABLE >= {"delete_document", "create_document", "delete_skill", "save_skill", "add_whiteboard_card", "delete_board_item", "map_from_note", "create_mindmap"}


def test_the_models_delete_skill_returns_the_same_undo(notebook):
    result = tools.execute_tool(notebook, "delete_skill", {"name": "Weekly tidy"})
    assert result["undo"]["tool"] == "save_skill"
