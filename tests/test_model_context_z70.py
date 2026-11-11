"""Audit 1030 Z70 (the model's context, model on): every note in the
prompt opened with "[Uncategorised]", a label that tells the model nothing
and spends its window. A note in no category goes in with no label; a
named category keeps its label, in both prompts (with tools and without)."""

from __future__ import annotations

import pytest

from tessellate.ai import librarian
from tessellate.ai import agent_turn


def _note(category: str) -> dict:
    return {"id": 7, "category": category, "content": "Dentist check-up booked for the 21st.", "tags": []}


def _prompt(build, category: str) -> str:  # noqa: ANN001
    messages = build("when is my dentist appointment", [_note(category)])
    return "\n".join(str(m.get("content")) for m in messages)


BUILDS = pytest.mark.parametrize("build", [librarian.build_messages, agent_turn.build_agent_messages], ids=["plain", "tools"])


@BUILDS
@pytest.mark.parametrize("category", ["Uncategorised", "Uncategorized", "", None])
def test_no_category_is_no_label(build, category):
    said = _prompt(build, category)
    assert "[Uncategori" not in said and "[]" not in said and "[None]" not in said, said
    assert "Dentist check-up booked for the 21st." in said


@BUILDS
@pytest.mark.parametrize("category", ["Health", "Courses & study", "Work"])
def test_a_named_category_keeps_its_label(build, category):
    assert f"[{category}]" in _prompt(build, category)


LINKED = {"id": 8, "category": "Travel", "connected": True, "tags": [], "content": "Lisbon trip. " + "Flights and hotels, " * 60}


@BUILDS
def test_a_linked_note_that_did_not_match_goes_in_as_a_short_line(build):
    """Z70, the last half: a note that only arrived by a link retold in full
    what the question did not ask about. It keeps one short line."""
    messages = build("what is on my packing list", [_note("Travel"), LINKED])
    said = "\n".join(str(m.get("content")) for m in messages)
    assert "Lisbon trip." in said
    assert said.count("Flights and hotels") <= 14, said.count("Flights and hotels")
