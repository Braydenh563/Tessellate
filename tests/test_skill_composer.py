"""Skills run by the composer when no model runs (O7 rest; INBOX 904 B69:
"Can the composer run skills and do them well??").

Measured with no model on :8795 before: running "Summarise my week" answered
"There is nothing in these notes regarding “run” or “saved” or “skill”"; and
"What did I write in the last seven days?" found nothing ("regarding
“seven”") while "the last 7 days" read "You wrote three notes the last 7
days" (no "in")."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tessellate.ai import composer, skill_composer, skills
from tessellate.entry import manager

TODAY = date(2026, 10, 17)


def _notes():
    return [
        {"id": 1, "content": "# Golf\n\nNine holes with Sam.", "created_at": "2026-10-16T09:00:00"},
        {"id": 2, "content": "# Dentist\n\nCheck-up on Tuesday.", "created_at": "2026-10-12T09:00:00"},
    ]


@pytest.mark.parametrize(
    ("phrase", "said"),
    [
        ("the last 7 days", "in the last 7 days"),
        ("last 7 days", "in the last 7 days"),
        ("the past 3 weeks", "in the past 3 weeks"),
        ("past week", "in the past week"),
        ("the last seven days", "in the last seven days"),
        ("the last couple of days", "in the last couple of days"),
        ("the last week", "in the last week"),
        ("last week", "last week"),
        ("last month", "last month"),
        ("today", "today"),
        ("since 3 October", "since 3 October"),
    ],
)
def test_a_rolling_window_is_in_it(phrase, said):
    assert composer.window_said(phrase) == said


@pytest.mark.parametrize("asked", ["last 7 days", "last seven days", "past seven days", "past 7 days"])
def test_seven_days_is_read_in_digits_or_words(asked):
    p = composer.plan(f"What did I write in the {asked}?", TODAY)
    assert p.window == (date(2026, 10, 10), TODAY), p.window
    said = composer.compose(f"What did I write in the {asked}?", _notes(), today=TODAY)["text"]
    assert said.startswith("You wrote two notes in the "), said
    assert " in the in " not in said


# --- the skills the composer runs ---------------------------------------------------------

def _stream(client, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": body.pop("question", "run"), **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


@pytest.fixture()
def notebook(session):
    manager.create_entry(session, "# Golf\n\nNine holes with Sam on Saturday.", tags=["golf"])
    manager.create_entry(session, "# Dentist\n\nCheck-up on Tuesday. Ask about the night guard.")
    manager.create_entry(session, "# Meetings\n\nWeekly sync notes.", tags=["meeting"])
    manager.create_entry(session, "# Standup\n\nDaily sync notes.", tags=["meetings"])
    session.commit()
    return session


def test_the_shipped_skills_have_a_reading_or_say_they_need_a_model():
    names = {s["name"] for s in skills.builtins()}
    assert set(skill_composer.RUNS) <= names, set(skill_composer.RUNS) - names
    for skill in skills.builtins():
        assert skill_composer.can_run(skill) == (skill["name"] in skill_composer.RUNS)
    own = {"name": "Mine", "builtin": False, "steps": ["x"]}
    assert not skill_composer.can_run(own)
    assert not skill_composer.can_run({"name": "Summarise my week", "builtin": False})


def test_the_catalogue_says_which_skills_run_without_a_model(client):
    listed = {s["name"]: s for s in client.get("/skills").json()["skills"]}
    assert listed["Summarise my week"]["composer"] is True
    assert listed["Draft an email"]["composer"] is False


def test_summarise_my_week_is_answered_from_the_notes(client, notebook):
    out = _stream(client, skill="Summarise my week")
    assert "notes in the last 7 days" in out["text"] and "Golf" in out["text"], out["text"]
    assert out["meta"][0]["composed"] is True
    assert "regarding" not in out["text"]


def test_catch_up_on_a_topic_uses_the_topic(client, notebook):
    out = _stream(client, skill="Catch up on a topic", skill_inputs={"topic": "golf"})
    assert "Sam" in out["text"] and "Saturday" in out["text"], out["text"]


def test_tidy_suggestions_and_the_health_check_read_the_notebook(client, notebook):
    tidy = _stream(client, skill="Tidy suggestions")["text"]
    assert tidy.startswith("Tidy-ups, most worth doing first:") and "1. one note with no tag: say “tag my untagged notes”." in tidy
    assert "#meeting and #meetings look like one tag" in tidy and tidy.endswith("Say which you want done.")
    health = _stream(client, skill="Notebook health check")["text"]
    assert health.startswith("Your notebook has four notes.") and "- one note with no tag" in health
    assert "I changed nothing" in health


def test_auto_tag_my_notes_is_a_card_with_confirm(client, notebook):
    out = _stream(client, skill="Auto-tag my notes")
    assert out["text"], out
    assert out.get("act") or "tag" in out["text"].lower()


def test_find_loose_ends_runs_the_starter(client, notebook):
    assert _stream(client, skill="Find loose ends")["text"]


def test_a_skill_that_writes_says_it_needs_a_model(client, notebook):
    said = _stream(client, skill="Draft an email", skill_inputs={"to": "Sam", "about": "golf"})["text"]
    assert said.startswith("“Draft an email” writes in its own words, so it needs a model, and none is running.")
    assert "Summarise my week" in said and "Settings, Models" in said


def test_an_empty_notebook_is_said(client):
    assert "no notes yet" in _stream(client, skill="Tidy suggestions")["text"]
