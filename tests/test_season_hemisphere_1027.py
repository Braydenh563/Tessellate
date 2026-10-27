"""Seasons follow the place (the owner, 2026-10-27).

Summer was always June to August, which is winter in Sydney, Auckland and
Johannesburg. A season is now read in the person's hemisphere: southern for
en-AU, en-NZ, en-ZA and the other southern regions the app knows, northern
otherwise, with a Settings override (automatic, northern, southern) that
beats the locale. Meteorological seasons throughout, a season named with a
year starts in that year ("summer 2025" is December 2025 to February 2026
in the south, as "winter 2025" always was in the north).

The clock is Wednesday 21 October 2026, 10:00. No model runs."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import notebook_stats, recognise as rec
from tessellate.api import routes_chat
from tessellate.core import config
from tests.test_composer_classes_1026c import _SUMMER, _WINTER, _fill
from tests.test_composer_classes_1357 import NOT_FOUND, NOW
from tests.test_composer_route_688 import _ask

TODAY = dt.date(2026, 10, 21)
D = dt.date


@pytest.fixture(autouse=True)
def _reset_settings():
    """The hemisphere settings are process state: every test starts on automatic, no locale."""
    rec.configure_hemisphere("auto", None)
    yield
    rec.configure_hemisphere("auto", None)


# --- the locale decides -----------------------------------------------------


@pytest.mark.parametrize("locale", ["en-AU", "en-NZ", "en-ZA", "en_AU", "en-au", "EN-NZ", "es-AR", "es-CL", "pt-BR", "af-ZA", "af"])
def test_southern_locales(locale):
    assert rec.hemisphere_of(locale) == "south"


@pytest.mark.parametrize("locale", ["en-GB", "en-US", "en-CA", "en-IE", "en-IN", "fr-FR", "de-DE", "ja-JP", "es-MX", "es-ES", "", None])
def test_northern_and_unknown_locales(locale):
    assert rec.hemisphere_of(locale) == "north"


def _season(phrase, locale=None, tense=None):
    got = rec.span(phrase, TODAY, tense, locale=locale)
    return None if got is None else (got[0], got[1])


NORTH_SUMMER = (D(2026, 6, 1), D(2026, 8, 31))
NORTH_WINTER_GONE = (D(2025, 12, 1), D(2026, 2, 28))
SOUTH_SUMMER_GONE = (D(2025, 12, 1), D(2026, 2, 28))
SOUTH_SUMMER_COMING = (D(2026, 12, 1), D(2027, 2, 28))
SOUTH_WINTER = (D(2026, 6, 1), D(2026, 8, 31))


@pytest.mark.parametrize(
    "phrase,locale,want",
    [
        # Northern, as before.
        ("last summer", "en-GB", NORTH_SUMMER),
        ("last winter", "en-US", NORTH_WINTER_GONE),
        ("spring", "en-GB", (D(2026, 3, 1), D(2026, 5, 31))),
        ("last autumn", "en-GB", (D(2025, 9, 1), D(2025, 11, 30))),
        ("last summer", None, NORTH_SUMMER),
        # Southern: the same words, the other half of the year.
        ("last summer", "en-AU", SOUTH_SUMMER_GONE),
        ("last summer", "en-NZ", SOUTH_SUMMER_GONE),
        ("last summer", "en-ZA", SOUTH_SUMMER_GONE),
        ("next summer", "en-AU", SOUTH_SUMMER_COMING),
        ("last winter", "en-AU", SOUTH_WINTER),
        ("last winter", "en-ZA", SOUTH_WINTER),
        ("spring", "en-AU", (D(2026, 9, 1), D(2026, 11, 30))),
        ("this spring", "en-NZ", (D(2026, 9, 1), D(2026, 11, 30))),
        ("last autumn", "en-AU", (D(2026, 3, 1), D(2026, 5, 31))),
        ("last fall", "en-AU", (D(2026, 3, 1), D(2026, 5, 31))),
        ("in winter", "en-AU", SOUTH_WINTER),
        # A season with a year starts in that year, in either half.
        ("summer 2025", "en-GB", (D(2025, 6, 1), D(2025, 8, 31))),
        ("winter 2025", "en-GB", (D(2025, 12, 1), D(2026, 2, 28))),
        ("summer 2025", "en-AU", (D(2025, 12, 1), D(2026, 2, 28))),
        ("winter 2025", "en-AU", (D(2025, 6, 1), D(2025, 8, 31))),
    ],
)
def test_a_season_is_read_in_the_hemisphere_of_the_locale(phrase, locale, want):
    assert _season(phrase, locale, "past") == want


def test_a_season_in_progress_is_the_one_meant_in_either_half():
    # 21 October: spring is under way in the south, autumn in the north.
    assert _season("this spring", "en-AU") == (D(2026, 9, 1), D(2026, 11, 30))
    assert _season("this autumn", "en-GB") == (D(2026, 9, 1), D(2026, 11, 30))


# --- the setting beats the locale -------------------------------------------


def test_the_setting_beats_the_locale():
    rec.configure_hemisphere("south", None)
    assert _season("last summer", "en-GB", "past") == SOUTH_SUMMER_GONE
    rec.configure_hemisphere("north", None)
    assert _season("last summer", "en-AU", "past") == NORTH_SUMMER


def test_automatic_follows_the_locale_the_browser_reported():
    rec.configure_hemisphere("auto", "en-AU")
    assert _season("last summer", None, "past") == SOUTH_SUMMER_GONE  # no locale on the call
    assert _season("last summer", "en-GB", "past") == NORTH_SUMMER  # the call's own locale wins
    rec.configure_hemisphere("auto", "en-GB")
    assert _season("last summer", None, "past") == NORTH_SUMMER


def test_recognise_and_the_search_window_use_the_same_reading():
    anchor = dt.datetime(2026, 10, 21, 10)
    south = rec.question_day("what did I write last summer", TODAY, "en-AU")
    north = rec.question_day("what did I write last summer", TODAY, "en-GB")
    assert (south[0], south[1]) == SOUTH_SUMMER_GONE
    assert (north[0], north[1]) == NORTH_SUMMER
    spans = rec.recognise("notes from last summer", now=anchor, locale="en-AU", tense="past")
    assert spans and spans[0].value[:2] == SOUTH_SUMMER_GONE
    # The scope ends with the call: nothing leaks into the next one.
    assert _season("last summer", None, "past") == NORTH_SUMMER


# --- the composer, end to end ------------------------------------------------

_NOT_SOUTH_SUMMER = r"Beach day|Hello|Uni timetable|Gym routine|Lecture 5|Pasta bake"
_NOT_SOUTH_WINTER = r"Ski trip|Snow day|New year plans|Gym routine|Lecture 5|Spring clean"


@pytest.fixture
def ask_from(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW.replace(tzinfo=dt.timezone.utc))
    _fill(session, False)
    return lambda q, locale: _ask(client, q, notes_only=True, answer_from="notes", history=[], locale=locale)["text"]


def _check(said, must, never, q):
    ok = bool(re.search(must, said, re.I | re.S)) and not re.search(never + "|" + NOT_FOUND, said, re.I | re.S)
    assert ok, f"{q!r} -> {said[:500]!r}"


@pytest.mark.parametrize("q", ["notes from last summer", "what did I write last summer", "anything I saved during summer?"])
def test_the_composer_reads_a_southern_summer(ask_from, q):
    _check(ask_from(q, "en-AU"), _WINTER, _NOT_SOUTH_SUMMER, q)


@pytest.mark.parametrize("q", ["what did I write last winter", "notes from winter"])
def test_the_composer_reads_a_southern_winter(ask_from, q):
    _check(ask_from(q, "en-NZ"), _SUMMER, _NOT_SOUTH_WINTER, q)


@pytest.mark.parametrize("q", ["notes from last summer", "what did I write last summer"])
def test_the_composer_still_reads_a_northern_summer(ask_from, q):
    _check(ask_from(q, "en-GB"), _SUMMER, r"Ski trip|Snow day|Pasta bake|Gym routine|Lecture 5", q)


def test_the_setting_reaches_the_composer(client, ask_from):
    reply = client.put("/preferences", json={"season_hemisphere": "south"})
    assert reply.status_code == 200
    _check(ask_from("notes from last summer", "en-GB"), _WINTER, _NOT_SOUTH_SUMMER, "setting south, locale en-GB")


# --- Settings ---------------------------------------------------------------


def test_the_preference_defaults_to_automatic_and_round_trips(client):
    assert config.DEFAULT_PREFERENCES["season_hemisphere"] == "auto"
    reply = client.get("/preferences").json()["season_hemisphere"]
    assert reply == "auto"
    for value in ("south", "north", "auto"):
        reply = client.put("/preferences", json={"season_hemisphere": value})
        assert reply.status_code == 200
        reply = client.get("/preferences").json()["season_hemisphere"]
        assert reply == value
    reply = client.put("/preferences", json={"season_hemisphere": "sideways"})
    assert reply.status_code == 422


def test_the_reported_locale_is_kept_and_applied(client):
    reply = client.put("/preferences", json={"season_locale": "en-AU"})
    assert reply.status_code == 200
    reply = client.get("/preferences").json()["season_locale"]
    assert reply == "en-AU"
    assert _season("last summer", None, "past") == SOUTH_SUMMER_GONE


def test_the_settings_row_the_report_and_the_help():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-season-hemisphere"' in html
    for label in ("From my language and region", "Northern hemisphere", "Southern hemisphere"):
        assert label in html
    rows = (root / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert '"season_hemisphere"' in rows
    panes = (root / "frontend" / "js" / "settings-panes.js").read_text(encoding="utf-8")
    assert "season_locale" in panes
    guide = (root / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8") + (
        root / "src" / "tessellate" / "ai" / "help_chat.py"
    ).read_text(encoding="utf-8")
    assert "Seasons" in guide and "hemisphere" in guide
