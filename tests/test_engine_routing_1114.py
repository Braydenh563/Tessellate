"""Three routing defects the 1.5B run found (L114, 2026-11-14), each through the engine with no model:
"Remember that I prefer ..." is the remember act, not a note search; "Delete the tag X" with no tags
does not say "rename"; "Make a board called Launch" is a board act, not a search. Clock: 10 Nov 2026."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import act_registry, commands
from tessellate.core.database import Entry, WhiteboardObject

from tests.test_parity_acts_1110 import card_of, confirm, notebook, stream, undo  # noqa: F401

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.api import chat_said, chat_turn, routes_chat, routes_insights
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn, routes_insights):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.mark.parametrize("said", ["Remember that I prefer short answers", "remember that i like bullet points", "Remember that I want British spelling."])
def test_remember_is_the_remember_act_not_a_search(client, said):
    out = stream(client, said)
    card = card_of(out)
    assert [s["name"] for s in card["steps"]] == ["save_user_preference"]
    assert card["steps"][0]["arguments"]["preference"].lower().startswith("i ")
    assert "no notes" not in out["text"].lower()


def test_remember_with_notes_is_still_the_act(client, notebook):  # noqa: F811
    card = card_of(stream(client, "Remember that I prefer short answers"))
    assert card["steps"][0]["name"] == "save_user_preference"


def test_remember_a_fact_about_a_thing_is_still_a_note(client, notebook):  # noqa: F811
    out = stream(client, "Remember that the wifi router is in the hallway")
    assert card_of(out)["steps"][0]["name"] != "save_user_preference"


def test_delete_the_tag_with_no_tags_does_not_say_rename(client):
    text = stream(client, "Delete the tag X")["text"]
    assert "no tags" in text and "rename" not in text and "delete" in text, text


def test_rename_the_tag_with_no_tags_still_says_rename(client):
    assert "rename" in stream(client, "Rename the tag X to Y")["text"]


@pytest.mark.parametrize("said", ["Make a board called Launch", "create a whiteboard named Launch", "start a new board called Launch"])
def test_a_board_by_name_is_a_card_then_an_empty_board_and_undo_bins_it(client, notebook, said):  # noqa: F811
    before = {e.id for e in notebook.scalars(select(Entry))}
    card = card_of(stream(client, said))
    assert card["steps"][0]["name"] == "create_mindmap" and card["steps"][0]["arguments"] == {"title": "Launch", "kind": "board"}
    assert {e.id for e in notebook.scalars(select(Entry))} == before
    done = confirm(client, card)
    notebook.expire_all()
    made = [e for e in notebook.scalars(select(Entry)) if e.id not in before]
    assert len(made) == 1 and made[0].is_board and made[0].content.startswith("# Launch")
    assert not notebook.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == made[0].id)).all()
    undo(client, done)
    notebook.expire_all()
    assert all(e.deleted_at for e in notebook.scalars(select(Entry)) if e.id not in before)


def test_a_mind_map_is_still_a_map(client, notebook):  # noqa: F811
    assert "kind" not in card_of(stream(client, "make a mind map about sourdough"))["steps"][0]["arguments"]


def test_the_new_acts_are_in_the_registry():
    assert act_registry.ACTS["remember"].confirm and act_registry.ACT_TOOLS["remember"] == "save_user_preference"
    assert commands.RUNNABLE >= {"save_user_preference", "create_mindmap"}


def test_confirming_remember_suggests_and_undo_drops_it(client, session):
    from tessellate.core.database import UserPreference

    card = card_of(stream(client, "Remember that I prefer short answers"))
    assert not session.scalars(select(UserPreference)).all()
    done = confirm(client, card)
    session.expire_all()
    rows = session.scalars(select(UserPreference)).all()
    assert [(r.content, r.proposed, r.active) for r in rows] == [("I prefer short answers", True, False)]
    undo(client, done)
    session.expire_all()
    assert not session.scalars(select(UserPreference)).all()


@pytest.mark.parametrize(
    ("question", "fact"),
    [
        ("what is the date in 10 days", "10 days from today is Friday 20 November 2026."),
        ("what is the date today", "Today is Tuesday 10 November 2026."),
        ("how many days until the dentist", "The dentist is 41 days from today, on 21 December."),
        ("how many days until 21 december", "Monday 21 December 2026 is 41 days away."),
    ],
)
def test_a_date_question_with_a_model_up_hands_the_model_the_worked_fact(ai_client, fake_ollama, session, question, fact):
    """L819 (Z68): the engine's half. With a model running the model words the answer (decision 75), so the fact
    it is given must be right; 'couldn't find' can then only come from the model's own wording."""
    import json

    from tessellate.entry import manager

    manager.create_entry(session, "# Dentist\n\nCheck-up booked for 2026-12-21. Ask about the night guard.")
    session.commit()
    stream(ai_client, question, use_tools=False)
    assert fact in json.dumps(fake_ollama.chat_calls[-1])
