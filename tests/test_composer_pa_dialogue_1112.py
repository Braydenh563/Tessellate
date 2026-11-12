"""Composer ledger 1112, composer-dialogue (F13 a, h, i, j; F1), no model, clock Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
from tessellate.core.database import EntryLink
import tests._seed_fc_1110 as seed

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _ask(client, question, history):
    with client.stream("POST", "/chat/stream", json={"question": question, "history": history}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    meta = next((e for e in events if e.get("type") == "meta"), {})
    titles = [str(r.get("title") or r.get("content") or "")[:60] for r in meta.get("raw_results") or []]
    return {"text": text, "titles": titles, "frame": next((e["frame"] for e in events if e.get("type") == "frame"), None)}


def talk(client, *questions):
    """The answers to `questions` asked one after another with the history the page would send (objects and frame)."""
    history, said = [], []
    for question in questions:
        got = _ask(client, question, history[-4:])
        said.append(got["text"])
        turn = {"question": question, "answer": got["text"]}
        objects = [re.split(r"[:.!?]", t.rstrip("…"))[0].strip()[:80] for t in got["titles"]][:5]
        if objects:
            turn["objects"] = objects
        if got["frame"]:
            turn["frame"] = got["frame"]
        history.append(turn)
    return said


@pytest.fixture
def notebook(client, session):
    seed.seed(session)
    return lambda *questions: talk(client, *questions)


# --- F13 a -------------------------------------------------------------------


@pytest.mark.parametrize("question", ["who am I going with", "Who am I going with?", "who am i going with"])
def test_f13_a_who_am_i_going_with_is_read_from_the_trip_note(notebook, question):
    said = notebook(question)[0]
    assert said.startswith("Travelling with Sam"), said
    assert "Japan trip" in said, said


def test_f13_a_the_same_after_an_answer_about_something_else(notebook):
    assert notebook("when is the dentist", "who am I going with")[1].startswith("Travelling with Sam")


# --- F13 h -------------------------------------------------------------------


def test_f13_h_and_the_week_before_is_the_question_over_the_week_earlier(notebook):
    last, before = notebook("what did I write last week", "and the week before")
    assert "last week" in last.lower(), last
    assert before.startswith("You wrote five notes from 26 October to 1 November"), before
    assert "feeling pretty tired" not in before, "the mood note of 10 November is not in the week before"


# --- F13 i -------------------------------------------------------------------


@pytest.mark.parametrize("question", ["summarise my japan notes", "summarise my harbor notes"])
def test_f13_i_both_summaries_have_the_same_shape(notebook, question):
    said = notebook(question)[0]
    assert said.startswith("Here are your 4 matching notes, one short paragraph each:\n"), said
    assert said.count("\n- [**") == 4, said


# --- F13 j -------------------------------------------------------------------


def test_f13_j_the_links_of_a_note_a_command_just_opened(client, session, notebook):
    said = notebook("open my kyoto ideas note", "what links to it")
    assert "Kyoto ideas" in said[1] and "linked" in said[1], said


@pytest.mark.parametrize("follow", ["what's related", "why are they linked", "how is it connected"])
def test_f13_j_the_other_ways_to_ask_it(notebook, follow):
    said = notebook("open my kyoto ideas note", follow)[1]
    assert "Kyoto ideas" in said and "linked" in said, said


def test_f13_j_a_linked_note_is_listed_with_its_reason(client, session):
    seed.seed(session)
    from sqlalchemy import select

    from tessellate.core.database import Entry

    ids = {e.content.split("\n", 1)[0].lstrip("# "): e.id for e in session.scalars(select(Entry)).all()}
    session.add(EntryLink(source_entry_id=ids["Kyoto ideas"], target_entry_id=ids["Tokyo food list"], reason="same trip"))
    session.commit()
    said = talk(client, "open my kyoto ideas note", "what links to it")[1]
    assert "Tokyo food list" in said and "same trip" in said, said


# --- X4: B24 undo sentences, B26 Q5 title, B27 find-similar (built earlier; pinned together here on the chat route) ---


def test_x4_b24_every_confirm_names_both_buttons_and_undo_after_a_pin_takes_it_back(notebook):
    pinned, undone = notebook("pin the kyoto ideas note", "undo")
    assert "Confirm" in pinned and "Cancel" in pinned, pinned
    assert "Favourites" in undone and "Confirm" in undone, undone


def test_x4_b24_undo_with_no_act_before_it_gives_the_keys(notebook):
    assert "Ctrl+Z" in notebook("undo")[0]


def test_x4_b26_q5_called_x_with_y_keeps_the_whole_title(notebook):
    said = notebook("make a note called Christmas with mum, dad and Sara")[0]
    assert "“Christmas with mum, dad and Sara”" in said and "Confirm" in said, said


def test_x4_b27_similar_to_searches_the_topic_not_the_sentence(notebook):
    said = notebook("find notes simlar to my dentist one yk")[0]
    assert said.startswith("I found two notes about “dentist”"), said
