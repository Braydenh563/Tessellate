"""The meeting-prep brief (L-general-11): a reminder that names a person or a
topic the notebook knows (an extracted entity or a tag) brings the newest
notes about it when it fires, through `GET /reminders/{id}/brief`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.core import deps
from tessellate.core.database import Entity, EntityMention, Entry

#: Far enough ahead that the route's "not in the past" check never trips.
DUE = (datetime(2030, 1, 1, 9, 0, tzinfo=timezone.utc)).isoformat()


def _note(client, content: str, **extra) -> int:
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def _mention(name: str, *entry_ids: int, aliases=None) -> None:
    with deps.get_db().session() as session:
        entity = Entity(name=name, kind="person", aliases=aliases)
        session.add(entity)
        session.flush()
        for entry_id in entry_ids:
            session.add(EntityMention(entity_id=entity.id, entry_id=entry_id))
        session.commit()


def _age(entry_id: int, days: int) -> None:
    with deps.get_db().session() as session:
        session.get(Entry, entry_id).updated_at = datetime(2029, 6, 1) - timedelta(days=days)
        session.commit()


def _reminder(client, text: str, **extra) -> int:
    response = client.post("/reminders", json={"text": text, "due_at": DUE, **extra})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_named_person_brings_their_newest_notes(client):
    old, mid, new = (_note(client, f"Sam Lee {w} notes") for w in ("budget", "hiring", "launch"))
    _mention("Sam Lee", old, mid, new)
    for entry_id, days in ((old, 30), (mid, 10), (new, 1)):
        _age(entry_id, days)
    _note(client, "Sam Lee in the words but never extracted as a mention")
    brief = client.get(f"/reminders/{_reminder(client, 'Call Sam Lee about the launch')}/brief").json()
    assert brief["subjects"] == ["Sam Lee"]
    assert [n["id"] for n in brief["notes"]] == [new, mid, old]
    assert brief["notes"][0]["title"]


def test_an_alias_names_the_entity_and_the_card_holds_three(client):
    ids = [_note(client, f"Robert met about item {i}") for i in range(5)]
    _mention("Robert Hale", *ids, aliases=["Bob"])
    brief = client.get(f"/reminders/{_reminder(client, 'Meet Bob at 3')}/brief").json()
    assert brief["subjects"] == ["Robert Hale"] and len(brief["notes"]) == 3


def test_a_tag_is_a_topic(client):
    tagged = _note(client, "Quarterly numbers draft", tags=["budget"])
    _note(client, "Unrelated thought")
    brief = client.get(f"/reminders/{_reminder(client, 'Budget review meeting')}/brief").json()
    assert brief["subjects"] == ["budget"]
    assert [n["id"] for n in brief["notes"]] == [tagged]


def test_nothing_named_gives_an_empty_brief(client):
    _note(client, "Sam Lee notes", tags=["budget"])
    brief = client.get(f"/reminders/{_reminder(client, 'Water the plants')}/brief").json()
    assert brief == {"subjects": [], "notes": []}


def test_whole_words_only_and_short_names_skipped(client):
    entry = _note(client, "Al and Samantha")
    _mention("Al", entry)
    _mention("Sam", entry)
    brief = client.get(f"/reminders/{_reminder(client, 'Email Samantha and Alan')}/brief").json()
    assert brief["subjects"] == []


def test_the_reminders_own_note_and_private_notes_are_left_out(client):
    own = _note(client, "Sam Lee one to one agenda")
    private = _note(client, "Sam Lee salary")
    shown = _note(client, "Sam Lee project notes")
    _mention("Sam Lee", own, private, shown)
    with deps.get_db().session() as session:
        session.get(Entry, private).is_private = True
        session.commit()
    rid = _reminder(client, "One to one with Sam Lee", entry_id=own)
    assert [n["id"] for n in client.get(f"/reminders/{rid}/brief").json()["notes"]] == [shown]


def test_an_unknown_reminder_is_404(client):
    assert client.get("/reminders/999999/brief").status_code == 404
