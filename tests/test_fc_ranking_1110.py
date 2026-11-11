"""Composer audit 1110 (docs/roadmap/agent-remaining/fable-composer-1110.md), no model, clock Tuesday 10 November 2026, 09:00:

- F8 the note that defines the subject leads; a short title-less note never outranks it.
- F9 the agenda lists what is to be done, clause by clause: the plumber is in, a mood is out.
- F13 the smaller verified items."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
import tests._seed_fc_1110 as seed

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _ask(client, question, **body):
    parts = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    parts.append(event.get("delta", ""))
    return "".join(parts)


@pytest.fixture
def notebook(client, session):
    seed.seed(session)
    return lambda question, **body: _ask(client, question, **body)


# --- F8 ----------------------------------------------------------------------


def test_when_is_the_dentist_leads_with_the_dentist_note(notebook):
    said = notebook("when is the dentist")
    assert said.startswith("Check-up booked for 21 November"), said


def test_what_is_in_my_budget_is_a_budget_note(notebook):
    said = notebook("what's in my budget")
    assert "Japan trip" not in said and "Budget" in said, said


def test_what_am_i_reading_is_the_reading_list(notebook):
    said = notebook("what am I reading")
    assert "Piranesi" in said and "Check-up" not in said, said


def test_what_did_i_plant_is_the_garden_note(notebook):
    said = notebook("what did I plant")
    assert "tomatoes" in said and "idea" not in said.lower(), said


def test_what_did_mia_say_is_the_standup_line(notebook):
    said = notebook("what did mia say")
    assert "android build" in said, said


# --- F9 ----------------------------------------------------------------------


def test_the_agenda_lists_the_plumber_not_the_mood(notebook):
    said = notebook("what's due this week")
    assert "Plumber is coming Thursday between 8 and 10" in said, said
    assert "feeling pretty tired" not in said.split("(")[0], said


def test_today_is_not_the_mood_note(notebook):
    said = notebook("what's on today")
    assert "dated item" not in said, said


# --- F13 ---------------------------------------------------------------------


def test_f13a_who_am_i_going_with_is_not_the_profile_question(notebook):
    assert "none of them says anything about you" not in notebook("who am I going with")
    #: "who am i" is the name question now (address.py): it is answered from the
    #: profile, here with none saved, and not by the notes' profile reader.
    assert "Settings, Profile" in notebook("who am i")


def test_f13b_nothing_found_is_said_and_stops(notebook):
    said = notebook("do I have anything on france")
    assert "france" in said and "newest" not in said and "feeling pretty tired" not in said, said


def test_f13c_an_exact_title_opens_as_here_it_is(session):
    from tessellate.ai import commands

    seed.seed(session)
    exact = commands._plan_read(session, {"intent": "open", "about": "Kyoto ideas"})  # noqa: SLF001
    assert exact["line"].startswith("Here it is:"), exact["line"]
    near = commands._plan_read(session, {"intent": "open", "about": "kyoto"})  # noqa: SLF001
    assert near["line"].startswith("The closest note about"), near["line"]


def test_f13d_the_forgotten_rows_are_titles_without_a_word_count(notebook):
    said = notebook("what have I forgotten")
    assert "no words" not in said and "- [Statistics lecture 1](#/notes/15)" in said, said
