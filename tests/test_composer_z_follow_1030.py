"""Composer audit 2026-10-30, class 10 (docs/roadmap/agent-remaining/audit-1030-composer.md):
a follow-on keeps its subject, and every demonstrative is the open note."""

from __future__ import annotations

import pytest

from tests import _seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch)


@pytest.mark.parametrize(("open_id", "question", "lead"), [
    # Z54: this, here and it are the open note, not a search.
    (1, "what is this note about", "Your Lisbon trip note, in five points"),
    (1, "what's in here", "Your Lisbon trip note, in five points"),
    (12, "explain this", "Your Tom note"),
    (1, "describe this note", "Your Lisbon trip note"),
    (1, "tell me more", "Your Lisbon trip note"),
    (34, "who is this about", "This note does not name anyone"),
    # Z55: a note that is only a title says so from every path.
    (34, "summarise this", "Your note “Weekend plans” is only a title so far"),
    (35, "what is in this note", "Your note “Ideas” is only a title so far"),
    # A title-less one-liner is said once, not named by its own words.
    (22, "summarise this", "Your note of 27 October says: Need to call the bank about the card"),
    # Z33: state words about the open checklist are the note's.
    (2, "what is not done yet", "Still open here: Charger"),
    (2, "how many are left", "What is left in this note: Charger"),
    (2, "what have I done", "Done so far: Passport and Euros"),
    (32, "what's still open", "What is left in this note: Renew passport"),
    (13, "what do I need to bring", "This note does not keep a checklist, but it says: Bring the insurance card"),
])
def test_the_open_note_answers_questions_that_point_at_it(ask, open_id, question, lead):
    said, _ = ask(question, open_id=open_id)
    assert said.startswith(lead), said


def _turn(question, said, label):
    return {"question": question, "answer": said, "objects": [label]}


@pytest.mark.parametrize(("question", "expect", "absent"), [
    ("how much does it cost", "Flights cost $420", "Renewal"),
    ("when is it", "14 November", None),
    ("what did we decide about it", None, "Renewal"),
])
def test_z53_a_follow_on_keeps_the_note_the_last_answer_led_with(ask, question, expect, absent):
    first, _ = ask("what do I know about Lisbon")
    said, _ = ask(question, history=[_turn("what do I know about Lisbon", first, "Lisbon trip")])
    assert expect is None or expect in said, said
    assert absent is None or absent not in said, said


def test_z53_a_question_with_a_subject_of_its_own_is_not_pulled_back(ask):
    first, _ = ask("what do I know about Lisbon")
    said, _ = ask("how much is the rent", history=[_turn("what do I know about Lisbon", first, "Lisbon trip")])
    assert "$1,200" in said, said


@pytest.mark.parametrize(("first", "then", "lead"), [
    ("what is on 4 November", "what time", "Here's the exact date: Dentist appointment on 4 November 2026 at 9:30"),
    ("what is on 4 November", "when is it", "The day noted down: Dentist appointment on 4 November 2026"),
    ("what is on saturday", "who is it with", "Your own words: Coffee with Anna"),
])
def test_z53_a_follow_on_after_a_date_list_keeps_its_first_item(ask, first, then, lead):
    """A date list cites no sources; the links it wrote name what it was about."""
    said = ask(first)[0]
    said2 = ask(then, history=[{"question": first, "answer": said}])[0]
    assert said2.startswith(lead), said2


def test_z53_a_turn_without_sources_is_named_by_the_links_in_its_answer():
    from tessellate.api.routes_chat import ChatTurn

    turn = ChatTurn(question="q", answer="- Dentist on 4 November. ([Dentist](#/notes/13))\n- [**Diary: Saturday 25 October**](#/notes/37)")
    assert turn.objects == ["Dentist", "Diary"]
    assert ChatTurn(question="q", answer="no links", objects=["Kept"]).objects == ["Kept"]
