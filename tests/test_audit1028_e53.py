"""Audit 1028 E53: one greeting."""

from __future__ import annotations

import re

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


# --- E53: one greeting ----------------------------------------------------------------


@pytest.mark.parametrize("greeting", ["hello", "hi there", "hey", "hello there", "good morning", "hi"])
def test_a_greeting_is_answered_with_one_greeting(client, session, greeting):
    manager.create_entry(session, "# Budget\n\nRent is 650 a month.", category_name="Personal")
    session.commit()
    said = _said(client, greeting)
    assert len(re.findall(r"\b(?:good (?:morning|afternoon|evening)|hi there|hello|hey)\b", said, re.I)) <= 1, said


