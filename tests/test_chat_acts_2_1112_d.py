"""Switch the theme and a reminder against a time in a note (L-chat-28), both ways. The theme is the page's own
preference, so the server's step acknowledges it and the page applies it; the reminder takes its time from the
note's `EntryDate`. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from tessellate.ai import act_registry, commands
from tessellate.core.database import Reminder
from tessellate.entry import manager

from tests.test_chat_acts_2_1112_c import _fixed_now  # noqa: F401
from tests.test_parity_acts_1110 import card_of, confirm, stream, undo

NOW = datetime(2026, 11, 10, 9, 0)
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("sentence", "theme"),
    [("switch to dark mode", "dark"), ("turn on dark mode", "dark"), ("use the light theme", "light"), ("switch to dark", "dark"),
     ("turn off dark mode", "light"), ("please switch to the system theme", "system"), ("change to light mode", "light")],
)
def test_the_theme_sentence_is_read(sentence, theme):
    assert commands.read(sentence, NOW)["name"] == theme


@pytest.mark.parametrize("sentence", ["what is dark mode", "dark mode", "the dark theme looks great", "turn the heating on"])
def test_other_sentences_are_not_the_theme(sentence):
    assert (commands.read(sentence, NOW) or {}).get("intent") != "set_theme"


def test_the_theme_card_waits_and_its_undo_names_the_step_back(client):
    for use_tools in (None, True):
        card = card_of(stream(client, "switch to dark mode", use_tools=use_tools))
        assert card["steps"] == [{"name": "set_theme", "arguments": {"theme": "dark"}}]
        done = confirm(client, card)
        assert done["undo"] and done["undo"][0]["name"] == "set_theme"
        undo(client, done)


def test_an_unknown_theme_step_is_refused(client):
    result = client.post("/chat/command/run", json={"steps": [{"name": "set_theme", "arguments": {"theme": "plaid"}}]}).json()
    assert result["ok"] is False


def test_the_page_applies_the_theme_and_patches_the_undo():
    js = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    assert "function applyThemeSteps(steps, result)" in js and "applyThemeChoice(step.arguments.theme, true)" in js
    assert js.count("applyThemeSteps(") >= 4, "run, post and the typed yes all apply it"
    assert act_registry.ACTS["set_theme"].confirm and act_registry.ACTS["set_theme"].inverse == "set_theme"


# --- "an hour before the dentist" ------------------------------------------------------------


@pytest.fixture
def dentist(session):
    manager.create_entry(session, "# Dentist\n\nCheck-up tomorrow at 3pm.", category_name="Life")
    session.commit()
    return session


@pytest.mark.parametrize(
    ("sentence", "minutes", "what"),
    [("remind me an hour before the dentist", 60, "dentist"), ("remind me 30 minutes before my dentist appointment", 30, "dentist"),
     ("remind me half an hour before the meeting", 30, "meeting"), ("remind me a day before the dentist", 1440, "dentist")],
)
def test_the_offset_and_the_name_are_read(sentence, minutes, what):
    parsed = commands.read(sentence, NOW)
    assert parsed["anchor"] == {"minutes": minutes, "what": what, "phrase": parsed["anchor"]["phrase"]} and parsed["due_at"] is None


def test_a_plain_time_is_not_an_anchor():
    assert "anchor" not in commands.read("remind me to call mum tomorrow at 9", NOW)
    assert commands.read("remind me 10 minutes before it", NOW) is None or "anchor" not in commands.read("remind me 10 minutes before it", NOW)


def test_the_card_is_the_note_time_less_the_offset(client, dentist):
    out = stream(client, "remind me an hour before the dentist")
    card = card_of(out)
    step = card["steps"][0]
    assert step["name"] == "set_reminder" and step["arguments"]["due_at"].startswith("2026-11-11T14:00")
    assert "2:00 pm" in card["label"] or "14:00" in card["label"] or "2pm" in card["label"].replace(" ", ""), card["label"]
    dentist.expire_all()
    assert not dentist.scalars(select(Reminder)).all()
    done = confirm(client, card)
    dentist.expire_all()
    assert [r.due_at.replace(tzinfo=None) for r in dentist.scalars(select(Reminder))] == [datetime(2026, 11, 11, 14, 0)]
    undo(client, done)


def test_a_task_first_sentence_keeps_its_words(client, dentist):
    card = card_of(stream(client, "remind me to bring the form 30 minutes before the dentist"))
    assert card["steps"][0]["arguments"]["text"] == "Bring the form" and card["steps"][0]["arguments"]["due_at"].startswith("2026-11-11T14:30")


def test_no_time_in_the_notes_asks_for_it(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up soon.", category_name="Life")
    session.commit()
    out = stream(client, "remind me an hour before the dentist")
    assert not [e for e in out.get("act", []) if e.get("steps")]
    assert "When is it" in out["text"]
    assert not session.scalars(select(Reminder)).all()
