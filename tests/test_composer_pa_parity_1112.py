"""Composer ledger 1112, composer-parity (P1 preview gate, D28 naming parity). Fake transport; the model-on read of the
preview needs a real model and is left (see composerA-1112.md)."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer
from tessellate.entry import manager
from tests.test_composer_brief import LONG


def _stream(client, question: str, **body) -> list[dict]:
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _seed(session) -> None:
    manager.create_entry(session, LONG["content"])
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    session.commit()


def test_p1_a_well_backed_draft_is_still_shown_before_the_model(ai_client, fake_ollama, session):
    _seed(session)
    events = _stream(ai_client, "When is the boiler service due?", use_tools=False)
    assert "composed_preview" in [e["type"] for e in events]


def _as_pictures(monkeypatch, said: str):
    """Compose's real output with every grounding row read as `said` ("picture": the app's reading of an image)."""
    real = composer.compose

    def changed(*args, **kwargs):
        got = real(*args, **kwargs)
        got["grounding"] = [{**row, "said": said} for row in got.get("grounding") or []]
        return got

    monkeypatch.setattr(composer, "compose", changed)


def test_p1_a_draft_the_notes_do_not_back_is_not_shown_ahead_of_the_model(ai_client, fake_ollama, session, monkeypatch):
    """Sent first and replaced, a draft that mostly quotes how the app read pictures would flash a claim the notebook
    does not make: the judgement that marks the finished answer low (`grounding.composed_support`) gates it too."""
    _seed(session)
    _as_pictures(monkeypatch, "picture")
    events = _stream(ai_client, "When is the boiler service due?", use_tools=False)
    kinds = [e["type"] for e in events]
    assert "composed_preview" not in kinds
    assert "answer" in kinds, "the model still answers"


@pytest.mark.parametrize("said", ["quoted", "picture"])
def test_p1_the_gate_reads_the_judgement_the_finished_answer_carries(ai_client, fake_ollama, session, monkeypatch, said):
    _seed(session)
    _as_pictures(monkeypatch, said)
    kinds = [e["type"] for e in _stream(ai_client, "When is the boiler service due?", use_tools=False)]
    assert ("composed_preview" in kinds) is (said != "picture")


# --- D28: the name of a note with no heading is the same on every surface, and is what the model reads ---

#: Title-less (no "# " line) and headed notes, the shapes real notebooks hold.
CONTENTS = [
    "# Dentist\n\nCheck-up booked for 21 November.",
    "feeling pretty tired today, slept badly. need to prep for the stats exam this week",
    "landlord called back, plumber is coming thursday between 8 and 10",
    "- [ ] milk\n- [ ] eggs",
    "Ran 6km this morning.\nFelt good, knee a bit sore after.",
    "## Second level only\n\nbody",
]


def _surfaces():
    """Every place that names a note by its text, as (surface, function of the text)."""
    from tessellate.ai import activity, composer_figures, composer_frame, composer_notes, tool_say

    return {
        "composer_frame.note_title": lambda text: composer_frame.note_title(text),
        "composer_notes link": lambda text: composer_notes._link({"id": 1, "content": text}).split("**")[1],
        "composer_figures": lambda text: composer_figures._name_of(type("E", (), {"content": text})()),
        "tool_say row": lambda text: tool_say._name(text),
        "activity feed": lambda text: activity._title_of(text),
    }


@pytest.mark.parametrize("content", CONTENTS)
def test_d28_every_surface_names_a_note_the_same_way(content):
    """The words are one reader's; a surface may cut them to its own width (tool_say rows at 60), never rename them."""
    names = {surface: read(content) for surface, read in _surfaces().items()}
    whole = max((n.rstrip("…") for n in names.values()), key=len)
    assert all(whole.startswith(n.rstrip("…")) for n in names.values()), names


@pytest.mark.parametrize("content", CONTENTS)
def test_d28_the_name_the_composer_gives_is_in_the_text_the_model_reads(content):
    from tessellate.ai import composer_frame, librarian

    name = composer_frame.note_title(content).rstrip("…")
    read = librarian.note_for_prompt({"id": 1, "content": content}, librarian.UNTOOLED_NOTE_CHARS, can_fetch=False)
    words = lambda text: " ".join(text.lower().replace("#", " ").split())  # noqa: E731
    assert words(name) in words(read), (name, read)
