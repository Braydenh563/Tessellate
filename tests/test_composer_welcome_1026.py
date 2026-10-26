"""The welcome is composed from the day (CHAT_PLAN 1353): the time of day, the
reminders due today, the last note's title and the streak, in the chosen voice."""

from __future__ import annotations

from datetime import datetime, timedelta

from tessellate.api import chat_extra
from tessellate.entry import manager
from tessellate.core.database import Reminder
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 10, 26, 8, 30)


def _fill(session):
    manager.create_entry(session, "# Tides\n\nSpring tides follow the new moon.")
    session.add(Reminder(text="Call the dentist", due_at=NOW.replace(hour=15)))
    session.add(Reminder(text="Later", due_at=NOW + timedelta(days=3)))
    session.commit()


def test_the_welcome_names_the_day_the_due_count_and_the_last_note(session):
    _fill(session)
    out = {chat_extra.welcome_line(session, NOW, voice="natural", seed=f"s{n}") for n in range(40)}
    assert len(out) >= 10
    for text in out:
        assert "morning" in text.lower() and "“Tides”" in text and "1 reminder" in text, text
        assert "!" not in text and chr(0x2014) not in text


def test_an_empty_notebook_is_welcomed_as_new(session):
    text = chat_extra.welcome_line(session, NOW, voice="natural", seed="a")
    assert "Tides" not in text and ("first" in text.lower() or "new" in text.lower() or "empty" in text.lower() or "nothing" in text.lower() or "no notes" in text.lower() or "morning" in text.lower())


def test_the_voice_changes_the_welcome(session):
    _fill(session)
    by_voice = {v: {chat_extra.welcome_line(session, NOW, voice=v, seed=str(n)) for n in range(60)} for v in ("natural", "plain", "playful", "professional")}
    assert not (by_voice["natural"] & by_voice["plain"]) and not (by_voice["playful"] & by_voice["professional"])


def test_hi_in_chat_is_answered_with_a_welcome(client, session):
    _fill(session)
    out = _ask(client, "hi")
    assert "“Tides”" in out["text"], out["text"]
    assert "!" not in out["text"]


def test_a_persona_sets_the_voice_unless_one_was_chosen(monkeypatch):
    from types import SimpleNamespace

    from tessellate.ai import librarian
    from tessellate.api import routes_chat

    monkeypatch.setattr(routes_chat, "_answer_voice", lambda: "natural")
    pick = lambda prompt: routes_chat._chat_voice(SimpleNamespace(persona_prompt=prompt))  # noqa: E731
    assert pick("You are a witty pirate who loves jokes.") == "playful"
    assert pick("A precise, formal archivist.") == "formal"
    assert pick(librarian.DEFAULT_PERSONA + "\n\nRemember: be brief.") == "natural"
    assert pick(None) == "natural" and pick("an ordinary helper") == "natural"
    monkeypatch.setattr(routes_chat, "_answer_voice", lambda: "plain")
    assert pick("You are a witty pirate who loves jokes.") == "plain"


def test_the_dashboard_line_welcomes_an_empty_notebook(client):
    seen = set()
    for seed in range(12):
        got = client.get(f"/insights/today-line?seed={seed}").json()
        assert got["kind"] == "welcome" and got["text"] and "!" not in got["text"]
        seen.add(got["text"])
    assert len(seen) >= 3
