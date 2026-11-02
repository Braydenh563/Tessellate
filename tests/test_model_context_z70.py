"""Audit 1030 Z70 (the model's context, model on): every note in the
prompt opened with "[Uncategorised]", a label that tells the model nothing
and spends its window. A note in no category goes in with no label; a
named category keeps its label, in both prompts (with tools and without)."""

from __future__ import annotations

import pytest

from tessellate.ai import agent, librarian


def _note(category: str) -> dict:
    return {"id": 7, "category": category, "content": "Dentist check-up booked for the 21st.", "tags": []}


def _prompt(build, category: str) -> str:  # noqa: ANN001
    messages = build("when is my dentist appointment", [_note(category)])
    return "\n".join(str(m.get("content")) for m in messages)


BUILDS = pytest.mark.parametrize("build", [librarian.build_messages, agent.build_agent_messages], ids=["plain", "tools"])


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
