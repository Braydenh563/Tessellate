"""Decisions and action items found with no model (WORLD_CLASS 28.5 row 2,
Brief 81). The sample meeting (`fixtures/meetings/launch_sync.txt`) holds
three decisions and three action items among lines that are neither; the
rules find exactly those, read the day and the name through
`ai/recognise.py`, and a model, when there is one, rewords the same list.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import meeting_summary
from tessellate.entry import meetings

SAMPLE = (Path(__file__).parent / "fixtures" / "meetings" / "launch_sync.txt").read_text()
NOW = datetime(2026, 10, 7, 14, 0)


def _found(text: str, people=None) -> dict:
    return meetings.find_items(text, people, now=NOW)


def test_the_sample_meeting_gives_three_decisions_and_three_actions() -> None:
    found = _found(SAMPLE)
    assert [d["text"] for d in found["decisions"]] == [
        "After some back and forth we decided to move the public launch to November",
        "Everyone agreed that we keep one plan at nine pounds a month for the first year",
        "We will drop the Android tablet build for this release",
    ]
    assert [(a["owner"], a["due"]) for a in found["actions"]] == [
        ("Sam", "Friday 9 October 2026"),
        ("Priya", "Saturday 14 November 2026"),
        ("Alex", "Thursday 8 October 2026"),
    ]
    #: Every quote is in the notes word for word.
    assert all(item["quote"] in SAMPLE for item in found["decisions"] + found["actions"])


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("We decided to move the launch to November.", "decisions"),
        ("Everyone agreed that the beta stays invite only.", "decisions"),
        ("We will drop the tablet build.", "decisions"),
        ("Action: Priya to book the venue before 14 November.", "actions"),
        ("TODO: Alex updates the budget sheet tomorrow.", "actions"),
        ("Sam will send the revised deck by Friday.", "actions"),
        #: A checkbox is an action item already: not offered twice.
        ("- [ ] Ask @Jo about the invoice", None),
        ("Sam said the old venue was too small.", None),
        ("Priya, can you walk us through the pricing?", None),
        ("The weather was grim on Friday.", None),
    ],
)
def test_one_shape_per_line(line: str, kind: str | None) -> None:
    found = _found(line)
    kinds = [k for k in ("decisions", "actions") if found[k]]
    assert kinds == ([kind] if kind else [])


def test_the_owner_becomes_the_mention_an_action_item_is_read_by() -> None:
    (item,) = _found("Sam will send the deck by Friday.")["actions"]
    assert item["text"] == "@Sam will send the deck by Friday"
    lines = meeting_summary.as_lines({"decisions": [], "actions": [item]})
    #: Copied from the notes, so no citation: its own "by Friday" sets the
    #: reminder's day, and the owner is not written twice.
    assert lines["actions"] == ["- [ ] @Sam will send the deck by Friday"]
    (read,) = meetings.action_items(lines["actions"][0])
    assert read["owner"] == "Sam" and not read["cited"]


def test_an_attendee_named_under_an_action_mark_owns_it() -> None:
    (item,) = _found("Action: the venue is for Jo to book", ["Jo"])["actions"]
    assert item["owner"] == "Jo"


def test_merge_keeps_the_rules_list_and_the_model_words() -> None:
    rules = _found(SAMPLE)
    model = {
        "decisions": [{"text": "Launch moves to November", "quote": "we decided to move the public launch to November"}],
        "actions": [{"text": "Invite the press", "quote": "That's everything", "owner": None}],
        "dropped": 1,
    }
    merged = meeting_summary.merge(rules, model)
    assert merged["decisions"][0]["text"] == "Launch moves to November"
    assert len(merged["decisions"]) == 3
    assert len(merged["actions"]) == 4 and merged["actions"][-1]["text"] == "Invite the press"
    assert merged["dropped"] == 1


def test_a_line_already_written_is_not_offered_again() -> None:
    note = "## Action items\n\n- [ ] Send the deck @Sam by Friday\n"
    assert meetings.already_written(note, meetings.ACTIONS, "@Sam will send the deck")
    assert not meetings.already_written(note, meetings.ACTIONS, "@Priya to book the venue")


def test_the_route_answers_with_no_model(client) -> None:
    content = meetings.compose("Launch sync", "2026-10-07 14:00", ["Sam", "Priya", "Alex"], notes=SAMPLE)
    note = client.post("/entries", json={"content": content, "category": "Work"}).json()
    body = client.post(f"/entries/{note['id']}/meeting/summarise").json()
    assert body["by"] == "rules" and body["note"]
    assert len(body["decisions"]) == 3 and len(body["actions"]) == 3
    assert body["lines"]["actions"][0] == "- [ ] @Sam will send the revised deck to the client by Friday"


def test_the_route_keeps_the_list_when_the_model_fails(app_state, fake_ollama, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    def broken(*_a, **_k):
        raise RuntimeError("model went away")

    monkeypatch.setattr(meeting_summary, "summarise", broken)
    client = TestClient(create_app())
    content = meetings.compose("Launch sync", notes=SAMPLE)
    note = client.post("/entries", json={"content": content, "category": "Work"}).json()
    body = client.post(f"/entries/{note['id']}/meeting/summarise").json()
    assert body["by"] == "rules" and "could not" in body["note"]
    assert len(body["actions"]) == 3


def test_a_day_is_read_from_the_meeting_date(client) -> None:
    content = meetings.compose("Sync", "2026-03-02 10:00", notes="TODO: Alex updates the budget sheet tomorrow.")
    note = client.post("/entries", json={"content": content, "category": "Work"}).json()
    (item,) = client.post(f"/entries/{note['id']}/meeting/summarise").json()["actions"]
    assert item["due"] == "Tuesday 3 March 2026"


# gap5-1111: the audit INBOX 1618 asked for on the no-model writers. A line
# that says a thing is NOT decided, asks whether it was, or says a person will
# NOT do a task is not a decision or an action item.
@pytest.mark.parametrize(
    "line",
    [
        "We haven't decided who owns onboarding.",
        "Nobody agreed to the new schedule.",
        "The budget has not yet been agreed.",
        "Have we decided on the venue?",
        "Did we agree that Priya takes the minutes?",
    ],
)
def test_an_undecided_or_questioned_line_is_not_a_decision(line: str) -> None:
    assert _found(line)["decisions"] == []


@pytest.mark.parametrize(
    "line",
    [
        "Nobody objected, so we decided to move the launch.",
        "We agreed not to hire this quarter.",
        "It was agreed that Priya takes the minutes.",
    ],
)
def test_a_decision_with_a_negative_nearby_is_still_a_decision(line: str) -> None:
    assert len(_found(line)["decisions"]) == 1


def test_a_person_who_will_not_do_a_task_is_not_given_the_task() -> None:
    found = _found("Sam will not attend the review on Friday.\nSam will send the notes.\nPriya does not need to book the room.", ["Sam", "Priya"])
    assert [a["text"] for a in found["actions"]] == ["@Sam will send the notes"]
