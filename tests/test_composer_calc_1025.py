"""composer4: date maths and counts with no model, through recognise.py only.
Fixed clock: Wednesday 21 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import composer_calc, composer_study

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)


def run(q: str, seed: str = "s", notes: list | None = None) -> str:
    ctx = composer_study.Ctx(question=q, notes=notes or [], now=NOW, seed=seed, asked=q)
    reply = composer_calc.answer(ctx)
    return reply.text if reply else ""


#: (question, must match)
TABLE = [
    ("how many days until 12 Dec", r"\b52 days\b"),
    ("how many days until 12 december?", r"\b52 days\b"),
    ("days until 12 dec", r"\b52 days\b"),
    ("how many days till christmas", r"\b65 days\b"),
    ("how many weeks until christmas", r"9\.3 weeks|9 weeks"),
    ("how many sleeps until christmas", r"\b65\b"),
    ("how many days until new year", r"\b72 days\b"),
    ("how many days to go until 31 december 2026", r"\b71 days\b"),
    ("how many days since 1 october", r"\b20 days\b"),
    ("days since 1 october", r"\b20 days\b"),
    ("how long ago was 1 september", r"\b50 days\b"),
    ("how many weeks since 1 september", r"7\.1 weeks|7 weeks"),
    ("how many days ago was 1 october", r"\b20 days\b"),
    ("how many months until 12 december", r"1 month and 21 days|1 month"),
    ("how many days until tomorrow", r"\b1 day\b|tomorrow"),
    ("how many weeks between 1 nov and 25 dec", r"7\.7 weeks"),
    ("weeks between 1 november and 25 december", r"7\.7 weeks"),
]


@pytest.mark.parametrize("q,must", TABLE)
def test_date_counts(q, must):
    said = run(q)
    assert re.search(must, said), said


@pytest.mark.parametrize("q", ["how many days until my birthday", "how many days until the exam", "how many days until"])
def test_a_date_it_cannot_read_is_left_to_the_older_readers(q):
    assert run(q) == ""


def test_the_reading_is_said():
    assert "Read as" in run("how many days until 12 dec")


def test_countdown_wordings_vary():
    seen = {run("how many days until 12 dec", seed=f"s{i}").split("\n")[0] for i in range(40)}
    assert len(seen) >= 3


UNITS = [
    ("convert 100 f to c", r"37\.78"),
    ("2 hours in minutes", r"120"),
    ("5 stone in kg", r"31\.7"),
    ("how many ml in a cup", r"2[34]\d"),
    ("60 mph in km/h", r"96\.5"),
    ("3 acres in hectares", r"1\.2"),
    ("how many seconds in a day", r"86,?400"),
    ("5 miles to km", r"8\.05"),
    ("1 gallon in litres", r"3\.79"),
    ("10 oz in grams", r"283"),
]

ROUTE = [
    ("how many days until 12 Dec", r"52 days"),
    ("how many weeks until christmas", r"9\.3 weeks"),
    ("how many days since 1 october", r"20 days"),
    ("how long ago was 1 september", r"50 days"),
    ("how many days until new year", r"72 days"),
    ("what's 3 weeks before 12 dec", r"21 November"),
    ("what is 10 days after 1 november", r"11 November"),
] + UNITS


@pytest.fixture
def route_ask(client, monkeypatch):
    from tessellate.api import routes_chat
    from tessellate.core import config
    from tests.test_composer_route_688 import _ask
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    return lambda q: _ask(client, q, notes_only=True, answer_from="notes", history=[])["text"]


@pytest.mark.parametrize("q,must", ROUTE)
def test_through_the_route_in_notes_only_mode(route_ask, q, must):
    said = route_ask(q)
    assert re.search(must, said), said
    assert "couldn't find" not in said
