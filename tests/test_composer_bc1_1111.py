"""Batch BC1 of the composer audits (E56: a timer, a pomodoro and the clock are
an open of the Clock window, never a reminder or a note search). Opening a
window changes nothing: the person presses Start, so the press is the consent.
Fixed clock: Saturday 31 October 2026, 11:30."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import commands

NOW = dt.datetime(2026, 10, 31, 11, 30)


@pytest.mark.parametrize("text, minutes, tab", [
    ("set a timer for 25 minutes", 25, "timer"),
    ("start a timer for 10 min", 10, "timer"),
    ("timer 90s", 1.5, "timer"),
    ("start a pomodoro", 25, "timer"),
    ("set a 15 minute timer", 15, "timer"),
    ("countdown 2h", 120, "timer"),
    ("start a stopwatch", None, "stopwatch"),
    ("open the clock", None, "timer"),
    ("set a timer", None, "timer"),
])
def test_a_clock_ask_opens_the_clock(text, minutes, tab):
    got = commands.read(text, NOW)
    assert got and got["intent"] == "navigate" and got["surface"] == "clock"
    assert got.get("minutes") == minutes and got.get("tab") == tab


@pytest.mark.parametrize("text", ["remind me to start a timer at 5", "what is a pomodoro", "how long should a pomodoro be"])
def test_other_sentences_are_not_the_clock(text):
    got = commands.read(text, NOW)
    assert not (got and got.get("surface") == "clock")


def test_route_event_carries_the_length(client):
    from tests.test_composer_route_688 import _ask

    events = _ask(client, "set a timer for 25 minutes", use_tools=True)
    nav = events["navigate"][0]
    assert nav["surface"] == "clock" and nav["minutes"] == 25 and nav["tab"] == "timer"
    assert "25 minutes" in events["text"] and "Start" in events["text"]


# Z16: a question word the quoted line answers by its figure is not "missing".
@pytest.mark.parametrize("question", [
    "what is the oven temperature for the banana bread",
    "how hot should the oven be for banana bread",
    "what temp do I bake the banana bread at",
])
def test_a_temperature_quoted_leaves_no_missing_footer(client, session, monkeypatch, question):
    import tests._seed_1030 as seed

    seed.seed(session)
    text = seed.asker(client, monkeypatch, chat=False)(question)
    text = text[0] if isinstance(text, tuple) else text
    assert "175" in text
    assert "do not mention" not in text and "None of these" not in text and "say anything about" not in text
