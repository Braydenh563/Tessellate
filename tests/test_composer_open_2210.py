"""Ask with a note open (22-10 bug doc): the answer is about that note.

The report: "Ask tab replies are identical across notes, long, and list dates
and links instead of answering". "What's left to do?" asked with two different
notes open gave the same notebook-wide reply. The open note answers a question
that has no subject of its own, in a sentence or two of its own words.
"""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer, composer_open

TODAY = date(2026, 10, 25)

PLAN = {
    "id": 1,
    "content": (
        "# Harbor launch plan\n\nShip the mobile app on the 14th of next month. "
        "Three gates come first: beta feedback, onboarding, pricing.\n\n"
        "- [x] Beta invite list\n- [x] Crash reporting\n- [ ] Store listing copy\n- [ ] Launch email"
    ),
    "created_at": "2026-10-20T10:00:00Z",
    "category": "Work",
    "tags": ["harbor"],
}
TRIP = {
    "id": 2,
    "content": "# Lisbon trip\n\nTen days in May with Ana and Rui. The flight leaves on 3 May. Book the tram pass before we go.",
    "created_at": "2026-10-18T10:00:00Z",
    "category": "Travel",
    "tags": [],
}


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("What's left to do?", "left"),
        ("what should I do next", "left"),
        ("any action items?", "left"),
        ("what is still outstanding", "left"),
        ("What is the deadline?", "when"),
        ("when is it due", "when"),
        ("who is involved?", "who"),
        ("who is mentioned here", "who"),
        ("What's the main point?", "point"),
        ("key takeaways", "point"),
        ("what is the weather", ""),
        ("hello", ""),
    ],
)
def test_kind(question, kind):
    assert composer_open.kind(question) == kind


def test_a_named_subject_is_not_this_note():
    # "when is the dentist" names a thing: the open note answers only if it holds it.
    assert composer_open.reads_note("when is the dentist?", PLAN) is False
    assert composer_open.reads_note("when is the launch?", PLAN) is True
    assert composer_open.reads_note("what's left to do?", PLAN) is True


def test_left_lists_only_the_open_tasks():
    out = composer.open_note_answer("What's left to do?", PLAN, today=TODAY)
    assert out is not None
    assert "Store listing copy" in out["text"] and "Launch email" in out["text"]
    assert "Crash reporting" not in out["text"]
    assert len(out["text"]) < 300


def test_the_same_question_differs_across_notes():
    a = composer.open_note_answer("What's left to do?", PLAN, today=TODAY)["text"]
    b = composer.open_note_answer("What's left to do?", TRIP, today=TODAY)["text"]
    assert a != b
    assert "tram pass" in b.lower()


def test_when_gives_the_dated_sentence_not_every_date():
    out = composer.open_note_answer("When is the deadline?", PLAN, today=TODAY)
    assert "14th of next month" in out["text"]
    assert "Crash reporting" not in out["text"]
    out = composer.open_note_answer("When is the deadline?", TRIP, today=TODAY)
    assert "3 May" in out["text"]


def test_who_names_the_people_the_note_holds():
    out = composer.open_note_answer("Who is involved?", TRIP, today=TODAY)
    assert "Ana" in out["text"] and "Rui" in out["text"]


def test_nothing_to_report_is_said_plainly():
    out = composer.open_note_answer("What's left to do?", {"id": 3, "content": "# Idea\n\nA quiet note about clouds."}, today=TODAY)
    assert "nothing" in out["text"].lower() or "no " in out["text"].lower()
    out = composer.open_note_answer("who is involved?", {"id": 3, "content": "# Idea\n\nA quiet note about clouds."}, today=TODAY)
    assert "does not name anyone" in out["text"]


def test_every_quote_is_the_notes_own_words():
    out = composer.open_note_answer("What's left to do?", PLAN, today=TODAY)
    for row in out["grounding"]:
        assert row["sentence"].lower().rstrip(".") in PLAN["content"].lower()
        assert row["note_id"] == 1


def test_the_opening_varies_with_the_salt():
    openings = {composer.open_note_answer("What's left to do?", PLAN, today=TODAY, salt=str(i))["text"].split(":")[0] for i in range(12)}
    assert len(openings) >= 2


def test_no_em_dash_or_exclamation():
    for q in ("What's left to do?", "When is the deadline?", "Who is involved?"):
        for note in (PLAN, TRIP):
            text = composer.open_note_answer(q, note, today=TODAY)["text"]
            assert chr(0x2014) not in text and "!" not in text


# --- through /chat/stream ----------------------------------------------------------

import json  # noqa: E402

from tessellate.entry import manager  # noqa: E402


def _ask(client, question: str, **body) -> str:
    text = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text.append(event["delta"])
    return "".join(text)


def _two_notes(session):
    a = manager.create_entry(session, PLAN["content"])
    b = manager.create_entry(session, TRIP["content"])
    session.commit()
    return a.id, b.id


def test_ask_with_a_note_open_answers_from_that_note(ai_client, session):
    a, b = _two_notes(session)
    first = _ask(ai_client, "What's left to do?", open_note_id=a, notes_only=True, answer_from="notes")
    second = _ask(ai_client, "What's left to do?", open_note_id=b, notes_only=True, answer_from="notes")
    assert "Store listing copy" in first and "Launch email" in first
    assert "tram pass" in second.lower()
    assert first != second


def test_a_note_without_a_date_says_so_not_general_knowledge(ai_client, session):
    _, b = _two_notes(session)
    manager.create_entry(session, "# Clouds\n\nA quiet note about clouds.")
    session.commit()
    text = _ask(ai_client, "What is the deadline?", open_note_id=b + 1, notes_only=True, answer_from="notes")
    assert "does not give a date" in text
    assert "general knowledge" not in text


def test_a_question_naming_something_else_still_searches_the_notebook(ai_client, session):
    a, b = _two_notes(session)
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    session.commit()
    text = _ask(ai_client, "When is the dentist?", open_note_id=a, notes_only=True, answer_from="notes")
    assert "21st" in text


def test_main_point_of_the_open_note_is_a_summary_with_its_name(ai_client, session):
    a, _ = _two_notes(session)
    text = _ask(ai_client, "What's the main point?", open_note_id=a, notes_only=True, answer_from="notes")
    assert "untitled" not in text.lower()
    assert "harbor launch plan" in text.lower()
