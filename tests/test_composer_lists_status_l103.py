"""L103: a status, done or how-many-left question over a list note answers from its
boxes, not with the first quoted line of whichever note the search ranked first."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
import tests._seed_composer_1110 as seed
from tessellate.core import clock
from tessellate.entry import manager

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _post(client, question):
    body = {"question": question, "history": [], "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.parametrize(
    "question",
    ["what is the status of my to-do list", "status of the to do list", "what's done on my todo list", "how is my todo list going"],
)
def test_the_status_of_the_todo_list_is_its_boxes(client, session, question):
    seed.seed(session)
    said = _post(client, question)
    assert "Todo note has one of four checklist items done" in said and "[x] Book flights" in said, said


@pytest.mark.parametrize(
    ("question", "title", "left", "total"),
    [
        ("how many items are left on the shopping list", "Shopping", "Three", "four"),
        ("how many things are left on my todo list", "Todo", "Three", "four"),
        ("how many are still open on my todo list", "Todo", "Three", "four"),
        ("how many items are left on the to-do list", "Todo", "Three", "four"),
    ],
)
def test_how_many_left_counts_the_open_boxes(client, session, question, title, left, total):
    seed.seed(session)
    said = _post(client, question)
    assert f"{left} of {total} are still open on" in said and title in said, said
    assert "do not mention" not in said and "nothing in these notes" not in said.lower(), said


# --- who has what, over a list of "Name: thing" lines ---------------------------------

_LISTS = (
    ("# Potluck\n\n- Sam: salad\n- Priya: dessert\n- Mia: drinks\n- Tom: bread", "Social"),
    ("# Chores\n\n- [x] Sam: bins\n- [ ] Priya: dishes\n- [ ] Tom: laundry", "Home"),
)


@pytest.fixture
def lists(session):
    for n, (content, category) in enumerate(_LISTS):
        entry = manager.create_entry(session, content, category_name=category)
        entry.created_at = entry.updated_at = datetime(2026, 11, 1 + n, 10)
    session.commit()


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("who is bringing the salad", "Sam is bringing the salad."),
        ("who is bringing dessert", "Priya is bringing dessert."),
        ("who is doing the dishes", "Priya is doing the dishes."),
        ("whose turn is the laundry", "Tom’s turn for the laundry"),
        ("what is Mia bringing", "Mia is bringing drinks."),
        ("who still has chores to do", "Priya (dishes) and Tom (laundry) still have something to do"),
    ],
)
def test_who_and_what_questions_read_the_person_and_thing_lines(client, session, lists, question, said):
    got = _post(client, question)
    assert said in got and "You wrote" not in got and "Also" not in got, got


def test_who_is_bringing_what_is_the_table(client, session, lists):
    got = _post(client, "who is bringing what to the potluck")
    assert all(f"- {line}" in got for line in ("Sam: salad", "Priya: dessert", "Mia: drinks", "Tom: bread")), got


def test_a_name_and_thing_list_of_one_line_is_no_table(client, session):
    entry = manager.create_entry(session, "# Plans\n\n- Sam: salad", category_name="Social")
    entry.created_at = entry.updated_at = datetime(2026, 11, 1, 10)
    session.commit()
    assert "Sam is bringing the salad" not in _post(client, "who is bringing the salad")


def test_a_person_on_two_lists_is_said_on_both():
    from datetime import date

    from tessellate.ai import composer_digest

    notes = [
        {"id": n + 1, "content": content, "created_at": f"2026-11-0{n + 1}T10:00:00", "category": cat, "tags": []}
        for n, (content, cat) in enumerate(_LISTS)
    ]
    said = composer_digest.answer("what is Sam taking", notes, today=date(2026, 11, 10))["text"]
    assert "Sam has salad on Potluck and bins on Chores." in said, said
