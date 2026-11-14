"""A task added to the list note named for tasks is a checklist line on the note called that, run at
once with Undo, not a reminder that asks for a time (composer-r7 R3-33); with no
such note one is offered. "tick the first one" counts from the list the last
answer showed. Seed: `tests/_seed_1031c.py` (the task list note)."""

from __future__ import annotations


import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import task_acts
from tests._consent import confirmed


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch, chat=True)


def _note(client, title):
    return next(e for e in client.get("/entries").json() if str(e["content"]).startswith(f"# {title}"))


@pytest.mark.parametrize("said", ["add buy stamps to my todo", "add buy stamps to my to-do list", "put buy stamps on my todo list", "add buy stamps to my tasks"])
def test_the_line_lands_on_the_todo_note_with_undo(go, client, said):
    text, events = go(said)
    assert "reminder" not in text.lower(), text  # the waiting line ("Ready when you are") is the frame's own
    assert not _note(client, "Todo")["content"].rstrip().endswith("- [ ] Buy stamps"), "waits for Confirm (owner, 2026-11-10)"
    done = confirmed(client, list(events))
    ran = "".join(e["delta"] for e in done if e.get("type") == "answer")
    assert "reminder" not in ran.lower() and "when" not in ran.lower(), ran  # the run asks no time
    card = next(e for e in done if e.get("type") == "act")
    assert card.get("done") and card.get("undo"), card
    assert _note(client, "Todo")["content"].rstrip().endswith("- [ ] Buy stamps")


def test_a_line_already_open_is_said_not_added_twice(go, client):
    text, _ = go("add renew passport to my todo")
    assert "already open" in text, text
    assert _note(client, "Todo")["content"].count("Renew passport") == 1


def test_a_time_said_keeps_it_a_reminder(go):
    _, events = go("add buy stamps to my todo tomorrow")
    card = next(e for e in events if e.get("type") == "act")
    assert card["steps"][0]["name"] == "set_reminder", card


def test_no_todo_note_offers_to_make_one(client, monkeypatch):
    go = seed_c.asker(client, monkeypatch, chat=True)
    text, events = go("add buy stamps to my todo")
    card = next(e for e in events if e.get("type") == "act")
    assert card["steps"][0]["name"] == "create_note" and "- [ ] Buy stamps" in card["steps"][0]["arguments"]["content"], card
    assert not card.get("done"), "offered, waiting for Confirm"


LISTED = "You have 3 open:\n- Renew passport\n- **Book the dentist follow-up** (Todo)\n- Finish the cloud assignment"


@pytest.mark.parametrize("said, item", [("tick the first one", "Renew passport"), ("tick off the last one", "Finish the cloud assignment")])
def test_an_ordinal_points_at_the_last_list(go, said, item):
    text, events = go(said, history=[{"question": "what is open on my todo", "answer": LISTED}])
    assert item in text, text


def test_an_ordinal_with_no_list_says_so(go):
    text, _ = go("tick the first one")
    assert "list in front of me" in text, text


@pytest.mark.parametrize("about, nth", [("the first one", 1), ("second", 2), ("number 3", 3), ("last one", -1), ("the 2nd item", 2), ("buy stamps", None), ("first aid kit", None)])
def test_ordinal_of(about, nth):
    assert task_acts.ordinal_of(about) == nth


def test_item_in_reads_bullets_marks_and_links():
    assert task_acts.item_in(2, LISTED) == "Book the dentist follow-up"
    assert task_acts.item_in(4, LISTED) is None and task_acts.item_in(1, "no list here") is None


LONG = "You have 15 open:\n" + "\n".join(f"- Task number {n} here" for n in range(1, 16))


@pytest.mark.parametrize("said", ["tick the last one", "tick 14", "tick the 15th one"])
def test_a_list_past_twelve_items_is_still_acted_on(said):
    from datetime import datetime

    from tessellate.api.chat_said import acts_on_listed_task

    assert acts_on_listed_task(said, [{"answer": LONG}], datetime(2026, 11, 9, 9, 0)) is True


def test_the_shown_list_is_parsed_once_per_turn(monkeypatch):
    from datetime import datetime

    from tessellate.api.chat_said import acts_on_listed_task

    calls = []
    real = task_acts.items_in
    monkeypatch.setattr(task_acts, "items_in", lambda text: calls.append(1) or real(text))
    acts_on_listed_task("tick the last one", [{"answer": LONG}], datetime(2026, 11, 9, 9, 0))
    # One parse here, one inside acts.parse resolving the ordinal; was 12 here plus that one.
    assert len(calls) == 2
