"""Meeting notes, redesigned (INBOX 644).

One shape (`entry/meetings.py`), made by `POST /meetings`, read by
`GET /entries/{id}/meeting`; an action item becomes a real reminder with no
model; a meeting sits on the timeline at its own date; Summarise keeps only
the lines whose source words are in the note. The audit these answer is
docs/roadmap/archive/agent-remaining/meetings-644.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from tessellate.ai import meeting_summary
from tessellate.entry import meetings, properties
import pytest
from tests._clock import SUITE_LOCAL, SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)

NOTE = (
    "---\ntype: Meeting\ndate: 2026-10-07 14:00\nattendees: [Sam, Priya]\n---\n"
    "# Weekly sync\n\n## Agenda\n\n1. Budget\n\n## Notes\n\n"
    "We went over the budget. Launch moves to November. Sam will send the deck.\n\n"
    "## Decisions\n\n- \n\n## Action items\n\n- [ ] Send the deck @Sam by Friday\n"
    "- [x] Book the venue\n- [ ] \n"
)


# --- the shape -------------------------------------------------------------


def test_compose_writes_the_one_shape() -> None:
    text = meetings.compose("Weekly sync", "2026-10-07 14:00", ["Sam", "@Priya", "sam", " "], ["Budget", ""])
    props, body = properties.split(text)
    assert props["type"] == ["Meeting"]
    assert props["date"] == ["2026-10-07 14:00"]
    assert props["attendees"] == ["Sam", "Priya"]
    assert body.startswith("# Weekly sync\n")
    for heading in ("## Agenda", "## Notes", "## Decisions", "## Action items"):
        assert heading in body
    assert "1. Budget" in body
    assert body.rstrip().endswith("- [ ]")
    assert meetings.is_meeting(text)


def test_compose_with_nothing_still_names_the_note() -> None:
    props, body = properties.split(meetings.compose(""))
    assert body.startswith("# Meeting\n")
    assert props["date"] == []


def test_is_meeting_by_type_or_tag() -> None:
    assert meetings.is_meeting("plain", ["Meeting"])
    assert meetings.is_meeting("---\ntype: meeting\n---\nx")
    assert not meetings.is_meeting("---\ntype: Book\n---\nx", ["work"])


def test_action_items_read_owner_done_and_line() -> None:
    items = meetings.action_items(NOTE)
    assert [i["text"] for i in items] == ["Send the deck @Sam by Friday", "Book the venue"]
    assert items[0]["owner"] == "Sam" and not items[0]["done"]
    assert items[1]["done"] and items[1]["owner"] is None
    lines = NOTE.split("\n")
    assert lines[items[0]["line"]] == "- [ ] Send the deck @Sam by Friday"


def test_an_email_is_not_an_owner_and_a_cite_is_not_the_task() -> None:
    text = "- [ ] Mail sam@example.com the deck, from “Sam will send the deck”\n"
    (item,) = meetings.action_items(text)
    assert item["owner"] is None
    assert item["text"] == "Mail sam@example.com the deck"
    assert item["cited"]


def test_section_items_and_aliases() -> None:
    assert meetings.section_items(NOTE, meetings.DECISIONS) == []
    assert meetings.section_items(NOTE, meetings.ACTIONS) == ["Send the deck @Sam by Friday", "Book the venue"]
    old = "Meeting about x\n\n## To do\n\n- [ ] Call Ana\n"
    assert meetings.section_items(old, meetings.ACTIONS) == ["Call Ana"]


def test_append_replaces_the_placeholder_and_keeps_the_rest() -> None:
    out = meetings.append_to_section(NOTE, meetings.DECISIONS, ["- Launch in November"])
    assert "## Decisions\n\n- Launch in November\n\n## Action items" in out
    assert out.startswith("---\ntype: Meeting\n")
    out = meetings.append_to_section(out, meetings.DECISIONS, ["- Budget holds"])
    assert "- Launch in November\n- Budget holds\n\n## Action items" in out
    out = meetings.append_to_section(out, meetings.ACTIONS, ["- [ ] Draft the brief"])
    assert out.endswith("- [x] Book the venue\n- [ ] Draft the brief\n")
    assert out.count("- [ ] Send the deck @Sam by Friday") == 1


def test_append_adds_a_missing_section_at_the_end() -> None:
    out = meetings.append_to_section("# Chat\n\nSome words.\n", meetings.DECISIONS, ["- Yes"])
    assert out == "# Chat\n\nSome words.\n\n## Decisions\n\n- Yes\n"
    assert meetings.append_to_section("x", meetings.NOTES, ["  "]) == "x"


# --- the routes, with no model -----------------------------------------------


def test_new_meeting_is_a_tagged_typed_note(client) -> None:
    response = client.post(
        "/meetings",
        json={"title": "Weekly sync", "when": "2026-10-07T14:00", "attendees": ["Sam", "Priya"], "category": "Work"},
    )
    assert response.status_code == 201, response.text
    made = response.json()
    assert "meeting" in made["tags"]
    assert made["category"] == "Work"
    assert made["properties"]["type"] == ["Meeting"]
    assert made["properties"]["date"] == ["2026-10-07 14:00"]
    assert made["properties"]["attendees"] == ["Sam", "Priya"]
    #: Only what was asked: the type's empty `project` is not written.
    assert "project" not in made["properties"]
    assert made["title"] == "Weekly sync"


def test_a_bad_when_is_refused(client) -> None:
    refused = client.post("/meetings", json={"title": "x", "when": "next tuesday"})
    assert refused.status_code == 422


def test_a_meeting_made_from_its_type_carries_the_tag(client) -> None:
    made = client.post("/entries", json={"content": "# Retro", "note_type": "Meeting", "category": "Work"}).json()
    assert "meeting" in made["tags"]


def test_a_note_typed_meeting_by_its_text_carries_the_tag(client) -> None:
    """The Capture box's Meeting template writes `type: Meeting` itself."""
    made = client.post("/entries", json={"content": "---\ntype: Meeting\n---\n## Agenda\n", "category": "Work"}).json()
    assert "meeting" in made["tags"]


def _make(client, content=NOTE):
    return client.post("/entries", json={"content": content, "category": "Work", "tags": ["meeting"]}).json()


def test_read_meeting(client) -> None:
    note = _make(client)
    body = client.get(f"/entries/{note['id']}/meeting").json()
    assert body["is_meeting"] and body["date"] == "2026-10-07 14:00"
    assert body["attendees"] == ["Sam", "Priya"]
    assert [a["text"] for a in body["actions"]] == ["Send the deck @Sam by Friday", "Book the venue"]
    assert body["actions"][0]["reminder_id"] is None
    assert body["has_notes"]


def test_an_action_item_becomes_a_reminder_with_no_model(client) -> None:
    note = _make(client)
    line = client.get(f"/entries/{note['id']}/meeting").json()["actions"][0]["line"]
    response = client.post(f"/entries/{note['id']}/meeting/remind", json={"line": line, "tz_offset_minutes": 0})
    assert response.status_code == 201, response.text
    reminder = response.json()
    assert reminder["entry_id"] == note["id"]
    assert reminder["text"] == "Send the deck @Sam by Friday"
    due = datetime.fromisoformat(reminder["due_at"].replace("Z", "+00:00"))
    assert due.weekday() == 4  # Friday
    #: Pressed again: the same reminder, and the sheet says it is set.
    again = client.post(f"/entries/{note['id']}/meeting/remind", json={"line": line}).json()
    assert again["id"] == reminder["id"]
    listed = client.get(f"/entries/{note['id']}/meeting").json()["actions"][0]
    assert listed["reminder_id"] == reminder["id"]
    assert any(r["id"] == reminder["id"] for r in client.get("/reminders").json())


def test_an_item_with_no_time_asks_when(client) -> None:
    note = _make(client, NOTE.replace("- [x] Book the venue", "- [ ] Book the venue"))
    line = client.get(f"/entries/{note['id']}/meeting").json()["actions"][1]["line"]
    refused = client.post(f"/entries/{note['id']}/meeting/remind", json={"line": line})
    assert refused.status_code == 422
    assert "Say when" in refused.json()["detail"]
    made = client.post(f"/entries/{note['id']}/meeting/remind", json={"line": line, "when": "tomorrow at 9am"})
    assert made.status_code == 201, made.text
    assert made.json()["text"] == "Book the venue"


def test_a_changed_line_is_refused(client) -> None:
    note = _make(client)
    refused = client.post(f"/entries/{note['id']}/meeting/remind", json={"line": 0})
    assert refused.status_code == 409


def test_append_writes_through_the_notes_route(client) -> None:
    note = _make(client)
    response = client.post(
        f"/entries/{note['id']}/meeting/append",
        json={"section": "Decisions", "lines": ["- Launch in November"]},
    )
    assert response.status_code == 200, response.text
    assert "## Decisions\n\n- Launch in November\n\n## Action items" in response.json()["content"]
    stale = client.post(
        f"/entries/{note['id']}/meeting/append",
        json={"section": "Decisions", "lines": ["- Again"], "base_hash": "0" * 16},
    )
    assert stale.status_code == 409
    unknown = client.post(f"/entries/{note['id']}/meeting/append", json={"section": "Whatever", "lines": ["x"]})
    assert unknown.status_code == 422


def test_summarise_without_a_model_reads_by_rules_and_says_so(client) -> None:
    """28.5 row 2: no model is no longer a 503. The rules read the notes and
    the answer says, in one line, that they did."""
    note = _make(client)
    response = client.post(f"/entries/{note['id']}/meeting/summarise")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["by"] == "rules" and "local AI is off" in body["note"]
    #: "Sam will send the deck" is already "Send the deck @Sam by Friday".
    assert body["actions"] == []


# --- the timeline ------------------------------------------------------------


def test_a_meeting_sits_on_the_timeline_at_its_date(client) -> None:
    when = (SUITE_LOCAL + timedelta(days=3)).replace(hour=14, minute=0, second=0, microsecond=0)
    made = client.post(
        "/meetings", json={"title": "Planning", "when": when.strftime("%Y-%m-%dT%H:%M"), "category": "Work"}
    ).json()
    rows = client.get("/timeline", params={"kind": "note"}).json()["rows"]
    row = next(r for r in rows if r["id"] == made["id"])
    assert row["placed_by"] == "meeting"
    assert row["date"] == when.date().isoformat()
    assert row["time"] == "14:00"
    assert not row["preview"].startswith("---")
    assert "type: Meeting" not in row["preview"]
    assert row["preview"].startswith("# Planning")


def test_a_meeting_with_no_date_sits_where_it_was_written(client) -> None:
    made = client.post("/meetings", json={"title": "Undated", "category": "Work"}).json()
    rows = client.get("/timeline", params={"kind": "note"}).json()["rows"]
    row = next(r for r in rows if r["id"] == made["id"])
    assert row["placed_by"] == "written"


# --- Summarise keeps only cited lines ------------------------------------------


SOURCE = "We went over the budget. Launch moves to November. Sam will send the deck."


def test_parse_reply_keeps_lines_found_in_the_note() -> None:
    reply = "\n".join(
        [
            "DECISION | Launch in November | Launch moves to November",
            "DECISION | Hire two people | we agreed to hire two",
            "ACTION | Send the deck | Sam Lee | Sam will send the deck.",
            "ACTION | Send the deck | Sam | Sam will send the deck",
            "nonsense line",
            "DECISION | Too short | the",
        ]
    )
    result = meeting_summary.parse_reply(reply, SOURCE)
    assert [d["text"] for d in result["decisions"]] == ["Launch in November"]
    assert [a["text"] for a in result["actions"]] == ["Send the deck"]
    assert result["actions"][0]["owner"] == "Sam"
    assert result["dropped"] == 3
    lines = meeting_summary.as_lines(result)
    assert lines["decisions"] == ["- Launch in November, from “Launch moves to November”"]
    assert lines["actions"] == ["- [ ] Send the deck @Sam, from “Sam will send the deck”"]
    #: The cite is read off before the line is an action item again.
    (item,) = meetings.action_items(lines["actions"][0])
    assert item["text"] == "Send the deck @Sam" and item["owner"] == "Sam"


def test_none_is_an_empty_answer() -> None:
    assert meeting_summary.parse_reply("NONE", SOURCE) == {"decisions": [], "actions": [], "dropped": 0}


def test_summarise_with_a_model(app_state, fake_ollama) -> None:
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    client = TestClient(create_app())
    note = _make(client)
    fake_ollama.librarian_reply = (
        "DECISION | Launch in November | Launch moves to November\n"
        "ACTION | Invent a thing | | words that are nowhere\n"
    )
    response = client.post(f"/entries/{note['id']}/meeting/summarise")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lines"]["decisions"] == ["- Launch in November, from “Launch moves to November”"]
    assert body["actions"] == [] and body["dropped"] == 1
    assert body["by"] == "model" and body["note"] == ""
    #: Nothing was written: the note is as it was.
    kept = client.get(f"/entries/{note['id']}").json()
    assert kept["content"] == NOTE
