"""The person's own abbreviations (CHAT_PLAN B7): learned from the notes,
never from a dictionary, and used to search and to answer "what does CC
stand for?". The bar the row names: 20 abbreviations resolved."""

from __future__ import annotations

import pytest

from tessellate.ai import glossary

#: Twenty ways a notebook says (or implies) what its abbreviations are.
NOTES = [
    "Intro to Cloud Computing starts Monday.", "CC assignment due Friday.",
    "Human Computer Interaction (HCI) lecture 2.",
    "DS = Data Structures, lab on Tuesday.",
    "OS stands for Operating Systems.",
    "PT means Personal Trainer at the gym.",
    "Saw the GP (general practitioner) about my knee.",
    "ML: machine learning reading group on Thursdays.",
    "Department of Health (DOH) letter came.",
    "Read the SRS - software requirements specification.",
    "PB is short for personal best.",
    "Weekly Review notes", "Did the WR on Sunday.",
    "Book the MRI (magnetic resonance imaging) for March.",
    "Started the Couch to 5K plan.",
    "Project Management Office sent the forms.", "PMO wants the forms back.",
    "Annual Leave starts 2 December.", "Put in the AL form.",
    "Supply Chain Management exam notes.", "SCM exam is in week 12.",
    "Quarterly Business Review (QBR) slides.",
    "The KPI (key performance indicator) is sign-ups.",
    "Research Methods reading.", "RM quiz on Friday.",
    "Statistics for Psychology tutorial.", "SfP homework is chapter 3.",
    "Customer Relationship Management (CRM) export.",
    "Work From Home Friday.", "WFH again tomorrow.",
    "Return on Investment for the ads.", "ROI looks bad.",
    "The ETA (estimated time of arrival) is 6pm.",
]

EXPECTED = {
    "CC": "Cloud Computing", "HCI": "Human Computer Interaction", "DS": "Data Structures",
    "OS": "Operating Systems", "PT": "Personal Trainer", "GP": "general practitioner",
    "ML": "machine learning", "DOH": "Department of Health", "SRS": "software requirements specification",
    "PB": "personal best", "WR": "Weekly Review", "MRI": "magnetic resonance imaging",
    "PMO": "Project Management Office", "AL": "Annual Leave", "SCM": "Supply Chain Management",
    "QBR": "Quarterly Business Review", "KPI": "key performance indicator", "RM": "Research Methods",
    "CRM": "Customer Relationship Management", "WFH": "Work From Home", "ROI": "Return on Investment",
    "ETA": "estimated time of arrival",
}


def test_twenty_abbreviations_are_resolved_from_the_notes():
    learned = glossary.learn(NOTES)
    right = {a for a, long in EXPECTED.items() if learned.get(a, "").lower() == long.lower()}
    assert len(right) >= 20, sorted(set(EXPECTED) - right)


def test_nothing_is_guessed():
    """A capital word with no phrase in the notes stays unknown, and a
    sentence that only uses one ("CC is due Friday") is not a definition."""
    learned = glossary.learn(["RSVP for the BBQ on Saturday.", "CC is due Friday.", "Met the PM about it.", "OK sounds good."])
    assert learned == {}


def test_two_phrases_with_the_same_initials_are_left_alone():
    learned = glossary.learn(["Cloud Computing lecture.", "Creative Commons licence.", "CC is on Friday."])
    assert "CC" not in learned


@pytest.mark.parametrize(("question", "searched"), [
    ("what's due in CC?", "what's due in CC Cloud Computing?"),
    ("CC notes", "CC Cloud Computing notes"),
    ("what's due in Cloud Computing (CC)?", "what's due in Cloud Computing (CC)?"),
])
def test_a_question_is_searched_with_its_phrase(question, searched):
    assert glossary.expand(question, {"CC": "Cloud Computing"}) == searched


@pytest.mark.parametrize(("question", "abbr"), [
    ("what does CC stand for?", "CC"), ("what is HCI?", "HCI"), ("what's an MRI", "MRI"),
    ("what does DOH mean?", "DOH"), ("what is due?", None), ("what is Sam doing?", None),
])
def test_what_an_abbreviation_stands_for_is_asked(question, abbr):
    assert glossary.asked(question) == abbr


def _notes(*texts):
    return [{"id": i + 1, "content": c, "created_at": f"2026-09-{i + 1:02d}T10:00:00", "category": "Uni", "tags": []} for i, c in enumerate(texts)]


def test_the_answer_says_what_it_stands_for_and_how_it_knows():
    from datetime import date

    from tessellate.ai import composer_digest

    said = composer_digest.answer("what does HCI stand for?", _notes("Human Computer Interaction (HCI) lecture 2.", "HCI quiz Friday."), today=date(2026, 10, 11))
    #: The note is named, never by its day, and the day is said only when
    #: the question asks about time (INBOX 1441, the owner, 2026-10-29).
    #: A note's own title is named as it is, never "the Cloud computing" (composer-1031, `composer_frame._titled`).
    assert said["text"].startswith("HCI is short for Human Computer Interaction, from Human Computer Interaction (HCI) lecture 2."), said["text"]
    assert "You use HCI in two notes." in said["text"]
    seen = composer_digest.answer("what does CC stand for?", _notes("Intro to Cloud Computing starts Monday.", "CC lab on Friday."), today=date(2026, 10, 11))
    #: INBOX 1441 moved this line's intent: a note is never named by its day,
    #: and a one-line sentence is quoted, not worn as a title.
    assert seen["text"].startswith("CC looks like Cloud Computing: the note that starts “Intro to Cloud Computing starts Monday” names it in full."), seen["text"]
    assert seen["grounding"][0]["note_id"] == 1
    #: Unknown to the notes: no reading, the composer's answer stands.
    assert composer_digest.answer("what does XYZ stand for?", _notes("Nothing here about it.", "Or here."), today=date(2026, 10, 11)) is None


def test_the_route_searches_and_answers_with_the_notes_own_abbreviations(client, session):
    """"What's due in CC" finds the note that only says Cloud Computing, and
    "what does CC stand for?" is answered from the notes, with no model."""
    from tessellate.entry import manager
    from tests.test_composer_route_688 import _ask

    manager.create_entry(session, "Intro to Cloud Computing: the assignment is due 20 October.")
    manager.create_entry(session, "CC lab: set up the virtual machine.")
    manager.create_entry(session, "Dentist on Friday, ask about the night guard.")
    session.commit()
    out = _ask(client, "what does CC stand for?", notes_only=True, use_tools=False, answer_from="notes")
    assert out["text"].startswith("CC looks like Cloud Computing"), out["text"]
    due = _ask(client, "when is CC due?", notes_only=True, use_tools=False, answer_from="notes")
    assert "20 October" in due["text"], due["text"]
