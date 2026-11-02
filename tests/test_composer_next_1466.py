"""INBOX 1466, first part (the owner, Ask, no model): under a composed
answer only "Why this answer" showed. The follow-up strip draws a composed
answer's own `next` (`renderAskFollowups`, `composedNext`), and a digest
answer handed none. Every composed answer now hands two or three asks
about the subject asked, none of them the question itself and no two the
same question in other words."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_digest
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOTES = [
    ("my uni days this week are tuesday and thursday", "Courses & study", ["university"]),
    ("I had three lectures for my cloud computing class last week.", "Courses & study", ["university"]),
    ("had design class today for prototyping", "Courses & study", ["university"]),
    ("# Cloud computing\n\nNotes on cloud computing: IaaS, PaaS and SaaS.", "Courses & study", ["university"]),
    ("# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.", "Health", ["health"]),
    ("# Sourdough\n\nFed the starter; the loaf needs a darker crust.", "Cooking", ["baking"]),
]


@pytest.fixture
def asks(client, session):
    for text, category, tags in NOTES:
        manager.create_entry(session, text, category_name=category, tags=tags)
    session.commit()

    def build(question: str) -> list[str]:
        out = _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")
        grounding = out.get("grounding") or [{}]
        #: Without the cited note's own offers ("Open \u201cDentist\u201d"), which are
        #: the prose closing line turned into chips (tests/test_composer_foot_1466.py).
        return [q for q in grounding[0].get("next") or [] if "\u201c" not in q]

    return build


@pytest.mark.parametrize(("question", "subject"), [
    ("What have I saved about courses & study?", "university"),
    ("tell me about uni", "uni"),
    ("what did I do in design class", "design class"),
    ("when is the dentist", "dentist"),
    ("what about sourdough", "sourdough"),
    ("how many lectures did I have", "lectures"),
])
def test_a_composed_answer_hands_two_or_three_asks_about_its_subject(asks, question, subject):
    found = asks(question)
    assert 2 <= len(found) <= 3, found
    assert all(subject in q.lower() for q in found), found
    assert all(q.endswith("?") and q[:1].isupper() for q in found), found


@pytest.mark.parametrize("question", ["what did I do in design class", "when is the dentist", "how many lectures did I have"])
def test_no_ask_repeats_the_question_or_another_ask(asks, question):
    found = asks(question)
    keys = [composer_digest._ask_key(q) for q in found]
    assert len(set(keys)) == len(keys), found
    assert composer_digest._ask_key(question) not in keys, found


@pytest.mark.parametrize(("a", "b"), [
    ("What is the latest on design class?", "What's the latest on design class"),
    ("When did I write about lectures?", "When did I last write about lectures?"),
    ("What else have I saved about the dentist?", "what else have I saved about dentist"),
])
def test_one_question_in_other_words_is_one_chip(a, b):
    assert composer_digest._ask_key(a) == composer_digest._ask_key(b)


def test_an_answer_ends_on_one_offer_at_most(client, session):
    for text, category, tags in NOTES:
        manager.create_entry(session, text, category_name=category, tags=tags)
    session.commit()
    for question in ("What have I saved about courses & study?", "when is the dentist", "what did I do in design class"):
        said = _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")["text"]
        offers = re.findall(r"(?:^|\n)(?:Next, I can|Want me to|I can summarise|Say the word)[^\n]*", said)
        assert len(offers) <= 1, said
