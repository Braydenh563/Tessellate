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


# --- P25 F9: "this week" with no day names the plumber note and leaves the mood note out ---


@pytest.mark.parametrize("question", ["what's on this week", "what do I have this week", "anything this week"])
def test_p25_f9_this_week_lists_the_dated_note_and_not_the_mood_note(notebook, question):
    said = notebook(question)[0]
    assert "Plumber is coming Thursday between 8 and 10" in said and "Thursday 12 November" in said, said
    assert "tired" not in said.lower(), said


# --- F1: a follow-on reads what the last answer showed, whatever the notes are called ---


def test_f1_titles_with_commas_stay_whole_sides_of_a_which_is_follow_on():
    """Joined with commas the titles split into more sides than notes ("which is oldest" over four notes named three
    nonsense ones); each side is the title up to its comma, which names the note by its words."""
    from tessellate.ai import reading

    titles = ["feeling pretty tired today, slept badly", "landlord called back, plumber is coming", "Shopping"]
    got = reading._follow_place("which one is the oldest", "which one is the oldest", titles)
    assert got == "which is oldest, feeling pretty tired today, landlord called back or Shopping", got
    compare = reading._follow_place("compare those", "compare those", titles)
    assert compare == "compare feeling pretty tired today, landlord called back and Shopping", compare


def test_f1_which_one_is_the_oldest_over_titles_with_commas_answers_over_the_notes(client, session):
    seed.seed(session)
    titles = ["landlord called back, plumber is coming thursday between 8 and 10", "Shopping"]
    history = [{"question": "list all my notes", "answer": "Here are your eight newest notes, of 36 in all.", "objects": titles}]
    said = _ask(client, "which one is the oldest", history)["text"]
    assert "Shopping" in said and "oldest" in said, said
    assert "nothing mentions" not in said and "appear in your notes" not in said, said


# --- PAR1: the ways to ask whether the notes contradict each other all reach the dated changes of mind ---


@pytest.mark.parametrize("question", [
    "do my notes contradict each other", "are there any contradictions in my notes", "does any note disagree with another",
    "is anything in my notes inconsistent", "are any of my notes contradictory", "do any of my notes conflict",
])
def test_par1_contradiction_wordings_get_the_changes_of_mind(notebook, question):
    said = notebook(question)[0]
    assert "change of mind" in said, said
    assert "don't mention" not in said and "None of your notes" not in said, said
