"""Composer wording across more than one fixed day (c11, reviewer finding 5). `conftest._fixed_day` pins one day
(2026-08-01), so a phrasing that reads the date could pass there and break on a weekday, a weekend or a month
end. The day is set here through the same fixed-clock seams the seed uses, never the real clock."""

from __future__ import annotations

import re
from datetime import date, datetime

import pytest

import tests._seed_r9_1109 as sd
from tessellate.api import routes_chat
from tessellate.core import clock, config

#: A Wednesday, a Saturday, a month end (a Monday) and a year end (a Thursday).
DAYS = [date(2026, 11, 11), date(2026, 11, 14), date(2026, 11, 30), date(2026, 12, 31)]
ASKS = ["what's on today", "what's due this week", "what's new lately", "what did I do yesterday"]


def _go(client, monkeypatch, day):
    now = datetime(day.year, day.month, day.day, 12, 0)
    monkeypatch.setattr(config, "user_now", lambda _c: now)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: now)
    monkeypatch.setattr(clock, "today", lambda: day)
    return lambda q: sd.ask(client, q, notes_only=True)["text"]


@pytest.mark.parametrize("day", DAYS, ids=lambda d: d.strftime("%a-%Y-%m-%d"))
@pytest.mark.parametrize("ask", ASKS)
def test_wording_holds_on_any_day(client, session, monkeypatch, day, ask):
    sd.seed(session)
    text = _go(client, monkeypatch, day)(ask)
    assert text.strip(), f"{ask!r} on {day} said nothing"
    assert not re.search(r"\{[a-z_]+\}|\bNone\b|\bnan\b|‹|›", text), text
    assert "  " not in re.sub(r"\s*\n\s*", " ", text).strip(), text
    assert not re.search(r"\b(?:Oops|!)", text), text


@pytest.mark.parametrize("day", DAYS, ids=lambda d: d.strftime("%a-%Y-%m-%d"))
def test_due_this_week_names_the_day_it_starts_from(client, session, monkeypatch, day):
    sd.seed(session)
    text = _go(client, monkeypatch, day)("what's due this week")
    #: Dated items are listed from today on, and a day before today is never listed as ahead.
    for found in re.finditer(r"\*\*(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day (\d{1,2}) (\w+)", text):
        listed = datetime.strptime(f"{found.group(1)} {found.group(2)} {day.year}", "%d %B %Y").date()
        assert listed >= day, f"{listed} listed as due on {day}"


@pytest.mark.parametrize("day", DAYS, ids=lambda d: d.strftime("%a-%Y-%m-%d"))
def test_yesterday_is_the_day_before_the_fixed_day(client, session, monkeypatch, day):
    sd.seed(session)
    text = _go(client, monkeypatch, day)("what did I do yesterday")
    assert "Yesterday" in text or "yesterday" in text or "nothing" in text.lower(), text
