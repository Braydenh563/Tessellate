"""Audit 1028 E72: the Why trail counts the notes the answer used."""

from __future__ import annotations


import pytest

from tessellate.ai import why
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


# --- E72: the Why trail counts the notes the answer used -------------------------------


def test_a_why_trail_never_says_nothing_matched_when_the_answer_used_notes():
    rows = why.lines(intent="notes", mode=None, matched=0, used=2, composed=True, marks={"done": 0.1})
    text = " ".join(r["text"] for r in rows)
    assert "nothing matched" not in text and "2 notes matched" in text


def test_a_why_trail_still_says_nothing_matched_when_nothing_was_used():
    rows = why.lines(intent="notes", mode=None, matched=0, used=0, composed=True, marks={"done": 0.1})
    assert any("nothing matched" in r["text"] for r in rows)


@pytest.mark.parametrize("question", ["summarise my history essay notes", "summarise my history essay", "give me a summary of the history essay"])
def test_a_summary_answer_trail_names_the_notes_it_read(client, session, question):
    manager.create_entry(session, "# History essay\n\nThe causes of the First World War. The alliance system mattered.", category_name="Uni")
    session.commit()
    trail = _ask(client, question, use_tools=False)["why"][0]["lines"]
    text = " ".join(r["text"] for r in trail)
    assert "nothing matched" not in text, text
