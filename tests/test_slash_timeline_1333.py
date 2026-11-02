"""/today, /recent and the "nothing written today, your notes run from X to Y"
answer draw a small timeline strip under their words (INBOX 1333 b: "if it
says that I wrote no notes today and that my notes only go from one date to
another then it can graph that"). The strip is a `panel` event the lazy reply
kit draws with the Statistics card's spark line (reply-kit.js)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 9, 0)


@pytest.fixture()
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def _note(session, when: datetime, text: str = "A note") -> None:
    entry = manager.create_entry(session, f"# {text}\n\nBody of {text}.")
    entry.created_at = entry.updated_at = when
    session.commit()


def _strip(out: dict) -> dict:
    strips = [p for p in out.get("panel", []) if p["panel"] == "timeline"]
    assert len(strips) == 1, out.get("panel")
    return strips[0]


@pytest.fixture()
def spread(session):
    for when in (datetime(2026, 7, 16, 10), datetime(2026, 9, 1, 10), datetime(2026, 10, 16, 10)):
        _note(session, when, when.strftime("Note %d %b"))


def test_nothing_today_graphs_where_the_notes_run(client, clock, spread):
    out = _ask(client, "/today", use_tools=False)
    assert "today" in out["text"].lower() and "16 July" in out["text"]
    strip = _strip(out)
    assert (strip["by"], strip["from"], strip["to"], strip["title"]) == ("week", "16 Jul", "Today", "Notes per week")
    #: 107 days from 16 July to 30 October, a week a point; one note in each of three.
    assert len(strip["points"]) == 16 and sum(strip["points"]) == 3
    assert [strip["points"][i] for i in (0, 6, 13)] == [1, 1, 1] and strip["points"][-1] == 0


def test_notes_today_draw_the_day_by_the_hour(client, clock, spread, session):
    _note(session, datetime(2026, 10, 30, 8, 10), "Early")
    _note(session, datetime(2026, 10, 30, 9, 0), "Nine")
    strip = _strip(_ask(client, "/today", use_tools=False))
    assert (strip["by"], strip["from"], strip["to"]) == ("hour", "00:00", "23:00")
    assert len(strip["points"]) == 24 and strip["points"][8] == strip["points"][9] == 1 and sum(strip["points"]) == 2


def test_recent_draws_the_span_of_the_notes_it_lists(client, clock, spread):
    strip = _strip(_ask(client, "/recent 2", use_tools=False))
    assert (strip["by"], strip["from"], strip["to"]) == ("week", "1 Sep", "16 Oct")
    assert len(strip["points"]) == 7 and strip["points"][0] == strip["points"][6] == 1 and sum(strip["points"]) == 2


def test_made_a_span_with_notes_draws_it_by_the_day(client, clock, spread, session):
    _note(session, datetime(2026, 10, 28, 12), "Two days ago")
    strip = _strip(_ask(client, "/made last 7 days", use_tools=False))
    assert strip["by"] == "day" and strip["to"] == "Today" and sum(strip["points"]) == 1


def test_a_long_notebook_is_drawn_by_the_month(client, clock, spread, session):
    _note(session, datetime(2025, 1, 15, 10), "Long ago")
    strip = _strip(_ask(client, "/today", use_tools=False))
    assert (strip["by"], strip["from"]) == ("month", "15 Jan 2025") and len(strip["points"]) == 22 and sum(strip["points"]) == 4


def test_the_words_with_no_model_carry_the_strip_too(client, clock, spread):
    out = _ask(client, "what did I write today", use_tools=False)
    strip = _strip(out)
    assert strip["to"] == "Today" and sum(strip["points"]) == 3


def test_nothing_to_draw_draws_nothing(client, clock, session):
    assert "panel" not in _ask(client, "/today", use_tools=False)
    _note(session, datetime(2026, 10, 16, 10))
    #: One note is a point, not a line; a command that names no time has no strip.
    assert "panel" not in _ask(client, "/count", use_tools=False)
    assert "panel" not in _ask(client, "/tags", use_tools=False)


def test_the_reply_kit_draws_a_timeline_panel_with_the_stats_spark():
    kit = (ROOT / "frontend" / "js" / "reply-kit.js").read_text(encoding="utf-8")
    assert "timeline: (event) => replyTimelinePanel(event)" in kit
    body = kit.split("function replyTimelinePanel", 1)[1].split("\n}\n", 1)[0]
    assert "replySpark(" in body and "replyPanelShell(" in body and "event.points" in body
