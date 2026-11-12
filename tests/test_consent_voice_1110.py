"""A card nobody worded when it was drawn (a starter's, a model's proposal) is confirmed in the
confirmations' own frames, not the plain "Done: ..." (consent2-1110, left item 1)."""

from __future__ import annotations

import inspect

from tessellate.ai import acts
from tessellate.api import chat_agent
from tessellate.core.database import Entry

LABELS = [f"Tag {n} untagged notes with tags you already use" for n in range(2, 14)]


def test_an_unworded_card_is_confirmed_in_the_composers_frames(session):
    entry = Entry(content="# Wifi\n\nthe network is Bluegum")
    session.add(entry)
    session.commit()
    said = []
    for label in LABELS:
        steps = [{"name": "tag_note", "arguments": {"note_id": entry.id, "add": ["wifi"]}}]
        done = acts.run_said(session, label, steps, [], None)
        assert done["ok"], done
        said.append(done["summary"])
    assert any(not line.startswith("Done: ") for line in said), said
    assert all(line.endswith(".") and "Done: Done" not in line for line in said), said


def test_a_typed_yes_on_a_tool_call_uses_the_same_frames():
    lines = {acts.done_line(f"moved note {n} to the bin", f"Move note {n}") for n in range(30)}
    assert len(lines) > 1 and any(not line.startswith("Done: ") for line in lines), lines
    assert all(line.endswith(".") for line in lines)


def test_chat_agent_has_no_plain_done_left():
    assert 'f"Done: ' not in inspect.getsource(chat_agent)
