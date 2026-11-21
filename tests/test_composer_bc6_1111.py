"""Batch BC6 (audit 1107 composer rows E16 to R3-31, rechecked 2026-11-11).
E9: "who is older, Anna or Tom" compares ages from the notes, or says plainly
that the notes do not say. Every question runs through the digest then the
composer (no model), over a small fixed-clock notebook."""

from __future__ import annotations

import pytest

from tests._seed_r2_1107 import TODAY, _route_answer


def _pool(*texts: str) -> list[dict]:
    return [{"id": i, "content": t, "category": "Uncategorised", "tags": [], "created_at": f"{TODAY.isoformat()}T10:00:00Z"} for i, t in enumerate(texts, 1)]


def say(question: str, *texts: str) -> str:
    return _route_answer(question, _pool(*texts))["text"]


GIFT = "# Gift ideas\n\nAnna: a book. Tom: a scarf."


@pytest.mark.parametrize("question", ["who is older, Anna or Tom", "who's older, Anna or Tom", "who is older Anna or Tom", "Anna or Tom, who is older"])
def test_e9_two_ages_are_compared(question):
    said = say(question, "# Anna\n\nAnna is 34. She likes pottery.", "# Tom\n\nTom is 41 and lives in Leeds.", GIFT)
    assert "Tom is older" in said and "41" in said and "34" in said, said


def test_e9_younger_and_a_birth_year():
    said = say("who is younger, Anna or Tom", "# Anna\n\nAnna was born in 1990.", "# Tom\n\nTom was born in 1984.", GIFT)
    assert "Anna is younger" in said and "1990" in said and "1984" in said, said


def test_e9_one_age_missing_says_which():
    said = say("who is older, Anna or Tom", "# Anna\n\nAnna is 34.", GIFT)
    assert "Anna is 34" in said and "not say how old Tom is" in said, said


def test_e9_no_ages_says_so_and_never_answers_a_gift_line():
    said = say("who is older, Anna or Tom", GIFT, "# Tom\n\nTom is my friend.")
    assert "do not say how old Anna or Tom is" in said and "scarf" not in said, said


TODO_NOTE = "# Todo\n\n- [ ] Book MOT\n- [x] Pay council tax\n- [ ] Email landlord"
PACK = "# Lisbon packing list\n\n- [x] Passport\n- [ ] Charger"


@pytest.mark.parametrize("question", ["which tasks are done", "what tasks have I completed", "which items are ticked off", "what items did I tick"])
def test_e21_done_tasks_list_the_ticked_items_not_the_reminders(question):
    said = say(question, TODO_NOTE, PACK)
    assert "Pay council tax" in said and "Passport" in said and "reminder" not in said.lower(), said


@pytest.mark.parametrize("question", ["what isn't ticked on the todo", "what isn't ticked", "what isn't done"])
def test_e21_a_negated_state_lists_what_is_open(question):
    said = say(question, TODO_NOTE, PACK)
    assert "Book MOT" in said and "Email landlord" in said and "Pay council tax" not in said, said


def _stats_count(text: str) -> str:
    from tessellate.ai import notebook_stats

    return notebook_stats._held_word(text, text)  # noqa: SLF001


@pytest.mark.parametrize("question", ["sara comes up in how many notes", "in how many notes does sara appear", "how many notes have the word sara"])
def test_r3_35_a_comes_up_count_is_the_mention_count_of_the_word(question):
    assert _stats_count(question).lower() == "sara"


@pytest.mark.parametrize("question", ["what is in my todo", "what's on my todo", "what is on my todo list"])
def test_r3_31_no_todo_note_and_no_checklist_says_so_instead_of_the_only_note(question):
    said = say(question, "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May.")
    assert said.startswith("You have no note called Todo"), said


def test_r3_31_a_todo_note_or_any_checklist_is_still_read():
    assert "Book MOT" in say("what is in my todo", TODO_NOTE)
    assert "Charger" in say("what is in my todo", PACK) or "Passport" in say("what is in my todo", PACK)


def test_e21_r3_8_the_route_reads_the_checklist_not_the_reminders_or_the_agenda(client, session):
    from tessellate.entry import manager
    from tests.test_composer_route_688 import _ask

    manager.create_entry(session, TODO_NOTE)
    manager.create_entry(session, PACK)
    done = _ask(client, "which tasks are done")["text"]
    assert "Pay council tax" in done and "reminders waiting" not in done, done
    listing = _ask(client, "what is in my todo")["text"]
    assert "Book MOT" in listing and "dated item" not in listing, listing
