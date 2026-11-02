"""Audit 1028 E52: the screen-aware next step is a tip beside the answer, not a line of it.

An answer is saved, copied and read aloud as written, so a coaching line
("Shall we carry on with ...", "To get going, ask me ...") inside its text
was part of what the person was told. It travels as its own `tip` event.
"""

from __future__ import annotations

import json

import pytest

from tessellate.entry import manager
from tests._app_js import app_js_text


def _events(client, question, **body):
    got: list[dict] = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        got = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return got, "".join(e["delta"] for e in got if e["type"] == "answer")


@pytest.fixture
def dentist(session):
    note = manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    session.commit()
    return note.id


@pytest.mark.parametrize("question", ["when is the check-up", "what is booked for the dentist", "what do I need to ask the dentist"])
def test_the_next_step_is_a_tip_event_and_not_the_answers_last_line(client, dentist, question):
    events, text = _events(client, question, open_note_id=dentist, screen={"tab": "notes", "actions": ["Cleared a box"]})
    tips = [e for e in events if e["type"] == "tip"]
    assert len(tips) == 1 and "Dentist" in tips[0]["text"], events
    assert tips[0]["text"] not in text and "Shall we carry on" not in text and "pick up" not in text.lower()


def test_no_screen_no_tip(client, dentist):
    events, _text = _events(client, "when is the check-up")
    assert not [e for e in events if e["type"] == "tip"]


def test_the_page_draws_the_tip_outside_the_answer():
    kit = app_js_text()
    assert 'else if (event.type === "tip" && onTip) onTip(event);' in kit
    assert "onTip: (event) => { chatTip = event.text || \"\"; }," in kit
    assert 'tip.className = "muted answer-tip";' in kit and "recordsHolder.prepend(tip)" in kit
