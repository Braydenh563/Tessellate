"""The Questions page with no model (INBOX 1466).

The owner: "cna the composer do the questions better?? or do it at all??".
Measured before (five seeded notes, no model, "Read notes now"): 3 of 6
questions found, only the ones ending "?", and 0 answered although two later
notes answer two of them. Each class is tested on several phrasings: the
ways of asking without a "?", the questions not to keep (rhetorical, quoted,
pasted, a template's), and a later note on the same subject answering one.
Dates are fixed, never today's.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from tessellate.ai import facts, question_cues, questions
from tessellate.core.database import DerivedFact, Entry, EntryLink

DAY0 = datetime(2026, 9, 1, 9, 0)


def _asked(text: str) -> list[str]:
    return [c.text for c in facts.candidates(text) if c.kind == "question"]


def _note(session, content, day=0):
    entry = Entry(content=content, tags=json.dumps([]))
    entry.created_at = DAY0 + timedelta(days=day)
    entry.updated_at = entry.created_at
    session.add(entry)
    session.commit()
    return entry


def _rows(session, kind):
    return list(session.scalars(select(DerivedFact).where(DerivedFact.kind == kind, DerivedFact.deleted_at.is_(None))))


def _state(session) -> dict[str, str]:
    page = questions.listing(session, limit=50)
    return {row["text"]: row["state"] for row in page["items"]}


@pytest.mark.parametrize(
    "sentence",
    [
        "I wonder whether the raised bed gets enough sun.",
        "I still wonder if the van will pass its inspection.",
        "Wondering whether to move the dentist to Friday.",
        "Not sure if the boiler is still under warranty.",
        "I'm not sure whether the lease covers the garden.",
        "Need to find out who services the boiler.",
        "I have to figure out the train times to Leeds.",
        "Should I renew the car insurance with the same firm.",
        "How do I reset the router password without the box.",
        "What's the best way to back up the photos from my phone.",
        "Do I need a visa for the trip to Canada in May.",
        "I don't know whether the parcel was ever posted.",
        "- not sure what to cook for the party on Sunday",
    ],
)
def test_a_question_asked_without_a_question_mark_is_found(sentence):
    assert _asked(f"Notes. {sentence}") == [sentence]


@pytest.mark.parametrize(
    "sentence",
    [
        "The boiler is under warranty until next June.",
        "We found out the train leaves at nine on Friday.",
        "I know how to reset the router password now.",
        "She should call the bank about the fee tomorrow.",
        "I am sure the lease covers the garden as well.",
    ],
)
def test_a_statement_is_not_a_question(sentence):
    assert _asked(f"Notes. {sentence}") == []


@pytest.mark.parametrize(
    "sentence",
    [
        "Who knows what next year will bring for us?",
        "Why not try the new bakery on the corner?",
        "What could possibly go wrong with this plan?",
        "How hard can it be to fix a dripping tap?",
        "It is a lovely day for the beach, isn't it?",
        "The plan is to leave at nine sharp, right?",
    ],
)
def test_a_rhetorical_question_is_not_kept(sentence):
    assert _asked(f"Notes. {sentence}") == []


@pytest.mark.parametrize(
    "content",
    [
        "> Should I take the job in Leeds or stay here?",
        "Mum said:\n> I wonder whether the house will sell by spring.",
        '"Should I take the job in Leeds?" she asked me at dinner.',
    ],
)
def test_a_quoted_question_is_not_kept(content):
    assert _asked(content) == []


@pytest.mark.parametrize(
    "content",
    [
        "Read later https://example.com/plants\nHave you ever wondered why your plants die in winter? Most people water them too much.",
        "From www.example.org/money\nAre you sure your savings are working hard enough for you?",
        "Saved https://example.com/a. Not sure if you know how to sharpen a knife properly.",
    ],
)
def test_a_pasted_page_question_is_not_kept(content):
    assert _asked(content) == []


def test_a_question_of_my_own_beside_a_link_is_kept():
    assert _asked("Lamp https://example.com/lamp\nShould I buy this lamp for the study?") == [
        "Should I buy this lamp for the study?"
    ]


def test_a_template_question_in_three_notes_is_not_kept(session):
    for day in range(3):
        _note(session, f"Journal day {day}.\nWhat am I grateful for today?\nThe walk by the river.", day)
    _note(session, "Garden. Should I plant the beans before the end of May?", 4)
    facts.run(session, budget=20000)
    assert [row.text for row in _rows(session, "question")] == ["Should I plant the beans before the end of May?"]


def test_the_same_question_in_two_notes_is_still_asked(session):
    for day in range(2):
        _note(session, f"Day {day}. Should I call the bank about the fee?", day)
    facts.run(session, budget=20000)
    assert len(_rows(session, "question")) == 2


SEED = [
    "Garden plan. Should I plant the tomatoes in March or wait until April? I wonder whether the raised bed gets enough sun.",
    "Boiler. Not sure if the boiler is still under warranty. Need to find out who services it.",
    "The boiler warranty runs until June 2027, the installer confirmed it on the phone.",
    "Tomatoes went in on 2 April after the last frost, the raised bed gets six hours of sun.",
    "How do I reset the router password? What's the best way to back up the photos?",
]


def test_the_measured_notes_have_their_questions_found_and_answered(session):
    """The before sweep's five notes: 3 of 6 found and 0 answered before."""
    for day, content in enumerate(SEED):
        _note(session, content, day)
    facts.run(session, budget=20000)
    state = _state(session)
    assert state == {
        "Should I plant the tomatoes in March or wait until April?": "answered",
        "I wonder whether the raised bed gets enough sun.": "answered",
        "Not sure if the boiler is still under warranty.": "answered",
        "Need to find out who services it.": "open",
        "How do I reset the router password?": "open",
        "What's the best way to back up the photos?": "open",
    }
    warranty = next(r for r in _rows(session, "answered") if "warranty" in json.loads(r.payload)["other_text"])
    assert warranty.text.startswith("The boiler warranty runs until June 2027") and warranty.model == "local"


@pytest.mark.parametrize(
    ("asked", "stated"),
    [
        ("Need to find out when the car's MOT is due.", "The car's MOT is due on the third of March."),
        ("I wonder if the library opens on Sundays.", "The library opens on Sundays from ten until four."),
        ("Should I paint the hallway grey or white?", "Painted the hallway white in the end, grey looked cold."),
        ("Not sure whether the passport needs renewing.", "Checked the passport, renewing it is needed before July."),
        ("How do I descale the kettle?", "Descaled the kettle with vinegar and it works well now."),
    ],
)
def test_a_later_note_that_states_it_answers_the_question(session, asked, stated):
    question = _note(session, f"Notes. {asked}", 0)
    answer = _note(session, stated, 3)
    facts.run(session, budget=20000)
    rows = _rows(session, "answered")
    assert len(rows) == 1
    payload = json.loads(rows[0].payload)
    assert rows[0].entry_id == answer.id and payload["other_entry_id"] == question.id
    assert answer.content[rows[0].span_start : rows[0].span_end] == rows[0].text


@pytest.mark.parametrize(
    ("asked", "stated", "day"),
    [
        ("I wonder if the library opens on Sundays.", "The library opens on Sundays from ten until four.", -3),
        ("I wonder if the library opens on Sundays.", "The bakery opens early on most weekdays now.", 3),
        ("Should I paint the hallway grey or white?", "Bought a new grey coat in the sale today.", 3),
        ("Need to find out when the car's MOT is due.", "When is the car's MOT due this year?", 3),
    ],
)
def test_an_earlier_unrelated_or_asking_note_does_not_answer(session, asked, stated, day):
    _note(session, f"Notes. {asked}", 0)
    _note(session, stated, day)
    facts.run(session, budget=20000)
    assert _rows(session, "answered") == []


@pytest.mark.parametrize("linked", [False, True])
def test_between_linked_notes_one_shared_word_is_enough(session, linked):
    question = _note(session, "Trip. Not sure whether the ferry takes bikes.", 0)
    answer = _note(session, "Rang them: the ferry has a rack at the back for four.", 2)
    if linked:
        session.add(EntryLink(source_entry_id=answer.id, target_entry_id=question.id))
        session.commit()
    facts.run(session, budget=20000)
    assert len(_rows(session, "answered")) == (1 if linked else 0)


def test_a_note_written_after_an_earlier_run_answers_an_old_question(session):
    _note(session, "Boiler. Not sure if the boiler is still under warranty.", 0)
    facts.run(session, budget=20000)
    assert _rows(session, "answered") == []
    _note(session, "The boiler warranty runs until June 2027.", 4)
    facts.run(session, budget=20000)
    assert len(_rows(session, "answered")) == 1


def test_a_second_run_finds_nothing_twice(session):
    for day, content in enumerate(SEED):
        _note(session, content, day)
    facts.run(session, budget=20000)
    before = len(list(session.scalars(select(DerivedFact))))
    again = facts.run(session, budget=20000)
    assert again["derived"] == 0 and len(list(session.scalars(select(DerivedFact)))) == before


class _SaysNo:
    def chat(self, model, messages):
        return {"content": "no - it does not say"}


def test_with_a_model_the_model_decides_what_answers(session):
    """Decision 75: the rule matcher stands in only when there is no model."""
    _note(session, "Notes. I wonder if the library opens on Sundays.", 0)
    _note(session, "The library opens on Sundays from ten until four.", 3)
    facts.run(session, budget=20000, provider=_SaysNo(), model="m")
    assert _rows(session, "answered") == []


def test_the_questions_route_shows_them(client, session):
    for day, content in enumerate(SEED):
        _note(session, content, day)
    client.post("/night/run", json={"budget": 20000})
    page = client.get("/questions", params={"state": "answered"}).json()
    assert len(page["items"]) == 3


@pytest.mark.parametrize(
    ("question", "heading", "words"),
    [
        ("Need to find out who services it.", "Boiler", {"servi", "boile"}),
        ("Not sure if the boiler is still under warranty.", "Boiler", {"boile", "warra"}),
        ("How do I reset the router password?", "Home", {"reset", "route", "passw"}),
    ],
)
def test_the_subject_is_the_question_words_and_the_heading_when_thin(question, heading, words):
    assert question_cues.subject(question, heading) == words
