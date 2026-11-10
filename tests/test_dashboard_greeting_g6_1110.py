"""Composer audit 2, G6 (1110): the dashboard greets once, agrees with itself,
counts what it says and names a note by its title."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from tessellate.ai import composer_voice, greeting_compose as g
from tessellate.api import chat_extra
from tessellate.entry import manager

NOW = datetime(2026, 10, 26, 8, 30)
WELCOMING = ("Welcome back", "Hello again", "A fresh page")


def _headlines(facts: g.NotebookFacts) -> set[str]:
    out = set()
    for day in range(1, 29):
        for hour in range(24):
            out.add(g.compose(datetime(2026, 10, day, hour, 5), facts)[0])
    return out


def test_an_empty_notebook_is_never_welcomed_back():
    seen = _headlines(g.NotebookFacts())
    assert not seen & {"Welcome back", "Hello again"}


def test_a_fresh_page_is_said_only_when_nothing_is_written_today():
    seen = _headlines(g.NotebookFacts(total=20, today=2, days_since_last=0))
    assert "A fresh page" not in seen and not seen & {"Welcome back", "Hello again"}
    assert "A fresh page" in _headlines(g.NotebookFacts(total=20, today=0, days_since_last=2))


def test_the_dashboard_welcome_for_an_empty_notebook_does_not_greet_again(session):
    for n in range(30):
        text = chat_extra.welcome_line(session, NOW, voice="natural", seed=f"s{n}", bare=True)
        assert text and not text.startswith(("Good", "Welcome", "Hello")), text
        assert "welcome back" not in text.lower()


def test_chat_never_says_welcome_back_of_an_empty_notebook(session):
    for n in range(40):
        assert "welcome back" not in chat_extra.welcome_line(session, NOW, voice="natural", seed=f"s{n}").lower()


def _note(i: int, day: date, title: str = "Harbor launch date") -> dict:
    return {"id": i, "content": f"{title}\nThe launch is set for the first week of December.", "created_at": f"{day.isoformat()}T09:00:00", "category": "", "tags": []}


@pytest.mark.parametrize("count,banned", [(2, "A busy page"), (5, "filled a little")])
def test_the_size_word_follows_the_count(count, banned):
    today = date(2026, 11, 10)
    notes = [_note(i, today) for i in range(count)]
    for seed in range(30):
        assert banned not in composer_voice.today_line(notes, today=today, seed=seed)["text"]


def test_a_long_gap_is_not_a_fresh_page():
    today = date(2026, 11, 10)
    notes = [_note(1, today - timedelta(days=700))]
    for seed in range(30):
        text = composer_voice.today_line(notes, today=today, seed=seed)["text"]
        assert "The page is fresh" not in text


def test_the_today_line_quotes_the_title(client):
    from tessellate.core import deps

    with deps.get_db().session() as session:
        for i in range(2):
            manager.create_entry(session, "# Harbor launch date\n\nThe launch is set for the first week of December.")
        session.commit()
    texts = {client.get(f"/insights/today-line?seed={s}").json()["text"] for s in range(12)}
    assert texts and all("**" not in t for t in texts)
    assert any("“Harbor launch date”" in t for t in texts)
