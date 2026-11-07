"""Composer round 3, 2026-11-07 (audit-1107-composer-r3.md): readers that fire
on an everyday word, and frames wrapped round fragments. Every question runs
through `composer.compose` (the digest first, as the route does) over a small
notebook; no model (fake transport), fixed clock."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_property
from tests._seed_r2_1107 import TODAY, _route_answer

assert TODAY == date(2026, 11, 7)


def _pool(*texts: str, ago: int = 0) -> list[dict]:
    day = date.fromordinal(TODAY.toordinal() - ago).isoformat()
    return [{"id": i, "content": t, "category": "Uncategorised", "tags": [], "created_at": f"{day}T10:00:00Z"} for i, t in enumerate(texts, 1)]


def say(question: str, *texts: str, ago: int = 0) -> str:
    return _route_answer(question, _pool(*texts, ago=ago))["text"]


@pytest.mark.parametrize("question", [
    "what is the table number", "what is the seat number", "what is my lucky number", "what is the number",
    "number of notes about Sara", "how many cells", "what number is the bus",
])
def test_r3_2_a_bare_number_is_not_a_phone_number_without_a_person(question):
    assert composer_property.asked(question) == "", question


@pytest.mark.parametrize("question", [
    "what is Sara's number", "what is the number for the dentist", "what's mum's number", "give me Anna's phone number",
    "what is his number",
])
def test_r3_2_a_number_beside_a_person_or_business_is_a_phone_ask(question):
    assert composer_property.asked(question) == "phone", question


def test_r3_2_the_subject_keeps_the_way_it_was_written():
    assert composer_property.subject("what is Sara's number") == "Sara"
    assert composer_property.subject("what is the number for the dentist") == "the dentist"
    assert composer_property.subject("what is his number") == ""


def test_r3_2_a_person_no_note_gives_a_number_for_is_denied_in_the_notebooks_name():
    assert say("what is Sara's number", "Sara likes jazz", "Weekend: call Mum and meet Sara") == "None of your notes give a phone number for Sara."
    assert say("what is the number for the dentist", "Dentist check-up on 11 November") == "None of your notes give a phone number for the dentist."
