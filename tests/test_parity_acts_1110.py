"""Parity acts, both ways (CHAT_PLAN decision 75): delete or merge a category (with an Undo that
files the notes back), delete a tag, edit a note's text, turn a note's lines into reminders. Each
is a card the composer draws with no model and the model's tool parks for the same Confirm; none
acts before Confirm. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import commands, tools
from tessellate.api import chat_said, chat_turn, routes_chat, routes_insights
from tessellate.core.database import Category, Entry, Reminder
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn, routes_insights):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def notebook(session):
    manager.create_entry(session, "# Harbor launch plan\n\nShip the app on 14 December.", category_name="Work", tags=["harbor"])
    manager.create_entry(session, "# Budget\n\nQ4 numbers.", category_name="Work", tags=["harbor", "money"])
    manager.create_entry(session, "# Wifi\n\nNetwork is Bluegum-5G.\nRouter is in the hallway cupboard.", category_name="Life")
    manager.create_entry(session, "# Action items\n\n- [ ] book the venue\n- [ ] email the caterer\n- [x] pay the deposit\n", category_name="Work")
    session.commit()
    return session


def stream(client, question: str, **body) -> dict:
    out: dict = {}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                out.setdefault(event["type"], []).append(event)
    out["text"] = "".join(e["delta"] for e in out.get("answer", []))
    return out


def card_of(out: dict) -> dict:
    return next(e for e in out.get("act", []) if not e.get("cancel") and not e.get("settle"))


def confirm(client, card: dict) -> dict:
    response = client.post("/chat/command/run", json={"steps": card["steps"], "skipped": card.get("skipped") or [], "consent_id": card.get("consent_id")})
    assert response.status_code == 200, response.text
    return response.json()


def undo(client, done: dict) -> None:
    assert done["undo"], done
    undone = client.post("/chat/command/run", json={"steps": done["undo"]})
    assert undone.status_code == 200


def filed(session, title: str) -> str:
    session.expire_all()
    entry = next(e for e in session.scalars(select(Entry)) if (e.content or "").startswith(f"# {title}"))
    return manager.category_name_for(session, entry)


def category_names(session) -> set[str]:
    session.expire_all()
    return {c.name for c in session.scalars(select(Category))}


# --- the tools' own Undo ----------------------------------------------------------------


def test_delete_category_undo_files_the_notes_back(notebook):
    result = tools.execute_tool(notebook, "delete_category", {"name": "Work"})
    assert result["notes_moved"] == 3 and result.get("undo"), result
    assert "Work" not in category_names(notebook) and filed(notebook, "Budget") == "Uncategorised"
    steps = [{"name": result["undo"]["tool"], "arguments": result["undo"]["arguments"]}] if result["undo"]["tool"] != "batch" else [{"name": s["tool"], "arguments": s["arguments"]} for s in result["undo"]["steps"]]
    done = commands.run(notebook, steps)
    assert done["ok"], done
    assert filed(notebook, "Budget") == "Work" and filed(notebook, "Harbor launch plan") == "Work" and filed(notebook, "Wifi") == "Life"


def test_merge_categories_undo_splits_them_again(notebook):
    result = tools.execute_tool(notebook, "merge_categories", {"from": "Work", "into": "Life"})
    assert result["notes_moved"] == 3 and result.get("undo"), result
    assert filed(notebook, "Budget") == "Life"
    undo_step = result["undo"]
    steps = [{"name": undo_step["tool"], "arguments": undo_step["arguments"]}]
    assert commands.run(notebook, steps)["ok"]
    assert filed(notebook, "Budget") == "Work" and filed(notebook, "Wifi") == "Life"


def test_delete_tag_undo_puts_it_back_on_the_same_notes(notebook):
    result = tools.execute_tool(notebook, "delete_tag", {"name": "harbor"})
    assert result["entries_changed"] == 2 and result["undo"]["tool"] == "batch", result
    steps = [{"name": s["tool"], "arguments": s["arguments"]} for s in result["undo"]["steps"]]
    assert commands.run(notebook, steps)["ok"]
    notebook.expire_all()
    tagged = sorted(e.content.split("\n", 1)[0] for e in notebook.scalars(select(Entry)) if "harbor" in manager.entry_tags(e))
    assert tagged == ["# Budget", "# Harbor launch plan"]


def test_an_empty_category_deleted_is_made_again_by_undo(notebook):
    tools.execute_tool(notebook, "create_category", {"name": "Hobbies"})
    result = tools.execute_tool(notebook, "delete_category", {"name": "Hobbies"})
    assert result["undo"]["tool"] == "create_category"
    assert commands.run(notebook, [{"name": "create_category", "arguments": result["undo"]["arguments"]}])["ok"]
    assert "Hobbies" in category_names(notebook)


# --- the composer's sentences: a card, nothing done before Confirm, Undo after -----------


def test_delete_a_category_by_sentence(client, notebook):
    out = stream(client, "delete the category Work")
    card = card_of(out)
    assert "Work" in card["label"] and "3 notes" in card["label"], card["label"]
    assert "Work" in category_names(notebook)
    done = confirm(client, card)
    assert "Work" not in category_names(notebook) and filed(notebook, "Budget") == "Uncategorised", done
    undo(client, done)
    assert filed(notebook, "Budget") == "Work" and filed(notebook, "Harbor launch plan") == "Work"


@pytest.mark.parametrize("sentence", ["merge the categories Work and Life", "merge category Work into Life", "merge the Work and Life categories"])
def test_merge_two_categories_by_sentence(client, notebook, sentence):
    card = card_of(stream(client, sentence))
    assert card["steps"][0]["arguments"] == {"from": "Work", "into": "Life"}, card
    assert filed(notebook, "Budget") == "Work"
    done = confirm(client, card)
    assert filed(notebook, "Budget") == "Life" and "Work" not in category_names(notebook), done
    undo(client, done)
    assert filed(notebook, "Budget") == "Work" and filed(notebook, "Wifi") == "Life"


def test_delete_a_tag_by_sentence(client, notebook):
    card = card_of(stream(client, "delete the tag harbor"))
    assert "2 notes" in card["label"], card["label"]
    done = confirm(client, card)
    notebook.expire_all()
    assert not [e for e in notebook.scalars(select(Entry)) if "harbor" in manager.entry_tags(e)], done
    undo(client, done)
    notebook.expire_all()
    assert len([e for e in notebook.scalars(select(Entry)) if "harbor" in manager.entry_tags(e)]) == 2


def test_a_category_or_tag_that_is_not_there_is_said_not_planned(client, notebook):
    for sentence in ("delete the category Gardening", "delete the tag gardening", "merge the categories Work and Gardening"):
        out = stream(client, sentence)
        assert not out.get("act") and "found no" in out["text"], (sentence, out["text"])


@pytest.mark.parametrize("question", ["how do I delete a category", "what happens if I delete a tag", "can I merge categories?"])
def test_a_question_about_them_is_not_an_act(client, notebook, question):
    assert not stream(client, question).get("act")


def test_edit_a_notes_text_by_sentence_with_a_diff_and_undo(client, notebook):
    card = card_of(stream(client, "edit the wifi note: the network is Bluegum-6G"))
    assert any(i.startswith("Was: ") and "Bluegum-5G" in i for i in card["items"]) and any(i.startswith("Now: ") and "Bluegum-6G" in i for i in card["items"]), card["items"]
    wifi = next(e for e in notebook.scalars(select(Entry)) if e.content.startswith("# Wifi"))
    before = wifi.content
    done = confirm(client, card)
    notebook.expire_all()
    assert wifi.content == "# Wifi\n\nthe network is Bluegum-6G", wifi.content
    undo(client, done)
    notebook.expire_all()
    assert wifi.content == before


def test_text_to_reminders_asks_when_then_makes_one_per_open_line(client, notebook):
    asked = stream(client, "turn the action items into reminders")
    assert not asked.get("act") and "When should" in asked["text"], asked["text"]
    card = card_of(stream(client, "turn the action items into reminders for friday at 9am"))
    assert [s["arguments"]["text"] for s in card["steps"]] == ["book the venue", "email the caterer"], card["steps"]
    assert notebook.query(Reminder).count() == 0
    done = confirm(client, card)
    assert notebook.query(Reminder).count() == 2, done
    undo(client, done)
    notebook.expire_all()
    assert all(r.deleted_at for r in notebook.query(Reminder))


def test_run_a_skill_by_sentence_hands_the_page_the_models_own_event(client, notebook):
    from tessellate.ai.tools import tool_handoff

    out = stream(client, "run the daily review skill")
    event = out["run_skill"][0]
    assert event == tool_handoff.validate_run_skill({"name": "Daily review"}), event
    assert "Run the skill" in out["text"] and not out.get("act"), out["text"]


def test_a_skill_that_needs_details_or_is_not_there_is_said(client, notebook):
    assert "Skill menu" in stream(client, "run the draft an email skill")["text"]
    gone = stream(client, "run the nonexistent skill")
    assert "no skill called" in gone["text"] and not gone.get("run_skill"), gone["text"]


@pytest.mark.parametrize("question", ["how do I run a skill", "what is a skill", "run a skill", "run the skill"])
def test_a_question_or_a_bare_word_is_no_skill_run(client, notebook, question):
    assert not stream(client, question).get("run_skill")


def test_the_page_asks_before_either_path_starts_a_skill():
    """Composer and model hand the page the same `run_skill` event; the page shows the plan card
    ("Run the skill" / "Not now") and starts the run only on the press (nothing starts on its own word)."""
    from pathlib import Path

    turn = Path("frontend/js/chat-turn.js").read_text(encoding="utf-8")
    start = turn.index("if (handoff) {")
    block = turn[start:start + 1800]
    assert "planProposalCard" in block and "startSkill" in block and "setTimeout(() => startSkill" not in block, block


# --- the model path: the same acts, the same Confirm -------------------------------------


@pytest.mark.parametrize("tool", ["delete_category", "merge_categories", "delete_tag", "edit_note", "set_reminder"])
def test_the_models_tool_parks_for_the_same_confirm(tool):
    assert tools.needs_confirm(tool, {}) is True


def test_every_composer_act_here_maps_to_the_tool_the_model_has():
    from tessellate.ai import act_registry

    for intent, tool in (("delete_category", "delete_category"), ("merge_categories", "merge_categories"), ("delete_tag", "delete_tag"), ("edit_text", "edit_note"), ("to_reminders", "set_reminder")):
        assert act_registry.ACT_TOOLS[intent] == tool and act_registry.ACTS[intent].confirm and tool in tools.TOOLS


@pytest.mark.parametrize("sentence", ["turn my todo note into reminders for friday at 9am", "make reminders from my todo note for friday at 9am"])
def test_a_note_titled_todo_is_found_by_that_word(client, session, sentence):
    manager.create_entry(session, "# Todo\n\n- [ ] book the venue\n- [ ] email the caterer\n", category_name="Work")
    session.commit()
    card = card_of(stream(client, sentence))
    assert "Todo" in json.dumps(card)
    assert "2 reminders" in json.dumps(card) or "reminder" in json.dumps(card)
