"""R9-11 rest (composer audit round 9): a note found only by likeness is not counted or quoted as being about the
subject when another note holds the subject's own word ("cat" is not "fish", "boiler" is not "radiator").
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_the_cat_is_pickle_not_the_fish_diet(say):
    text = say("what do I know about the cat")
    assert "olive oil" not in text and "Pickle is our cat" in text


def test_the_boiler_is_not_the_radiator_note(say):
    text = say("anything about the boiler?")
    assert "radiator" not in text and "1.5 bar" in text
