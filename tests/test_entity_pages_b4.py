"""WORLD_CLASS_PLAN B4: person and project pages, derived from the entity layer.

KG5's entity page said where a name is said, what it is named with and the
dates its notes resolve. B4 adds what makes it a page about a person or a
project: its open items (a project's unticked tasks in its notes, a person's
tasks that name them, and the reminders on those notes), its notes by month
(a timeline), and the notes linked to its notes that do not name it. And it is
reachable from a mention: a note's Connections lists the names it says.

Every date is set by hand (a fixed clock), never read from the real one.
"""

from __future__ import annotations

from datetime import datetime

from tessellate.core.database import Entity, EntityMention, Entry, EntryLink, Reminder
from tests._app_js import app_js_text


def _note(session, text, when, *, private=False):
    entry = Entry(content=text, ai_confidence=0, is_private=private)
    session.add(entry)
    session.flush()
    entry.created_at = entry.updated_at = when
    return entry


def _entity(session, name, *entries, kind=None, aliases=None):
    entity = Entity(name=name, kind=kind, aliases=aliases)
    session.add(entity)
    session.flush()
    for entry in entries:
        session.add(EntityMention(entity_id=entity.id, entry_id=entry.id))
    session.commit()
    return entity.id


def test_a_project_page_lists_its_open_tasks_and_reminders(client, session):
    plan = _note(
        session,
        "Kiln upgrade plan\n- [ ] Order the new elements\n- [x] Measure the shelf\n- [ ] Ask Sam Lee about wiring",
        datetime(2026, 9, 3, 10),
    )
    other = _note(session, "Kiln upgrade budget agreed", datetime(2026, 10, 1, 9))
    session.add(Reminder(entry_id=plan.id, text="Book the electrician", due_at=datetime(2026, 11, 20, 9)))
    session.add(Reminder(entry_id=plan.id, text="Done already", due_at=datetime(2026, 9, 1, 9), done=True))
    kiln = _entity(session, "Kiln upgrade", plan, other, kind="project")
    page = client.get(f"/entities/{kiln}").json()
    tasks = [i["text"] for i in page["open_items"] if i["kind"] == "task"]
    assert tasks == ["Order the new elements", "Ask Sam Lee about wiring"]
    reminders = [i for i in page["open_items"] if i["kind"] == "reminder"]
    assert [r["text"] for r in reminders] == ["Book the electrician"]
    assert reminders[0]["entry_id"] == plan.id and reminders[0]["due_at"].startswith("2026-11-20")
    assert all(i["entry_id"] == plan.id for i in page["open_items"])


def test_a_person_page_lists_only_the_tasks_that_name_them(client, session):
    note = _note(
        session,
        "Studio week\n- [ ] Order the new elements\n- [ ] Ask Sam Lee about wiring\n- [ ] Send the rota @Sam",
        datetime(2026, 9, 3, 10),
    )
    session.add(Reminder(entry_id=note.id, text="Book the electrician", due_at=datetime(2026, 11, 20, 9)))
    session.add(Reminder(entry_id=note.id, text="Call Sam about the kiln", due_at=datetime(2026, 11, 21, 9)))
    sam = _entity(session, "Sam Lee", note, kind="person", aliases=["Sam"])
    page = client.get(f"/entities/{sam}").json()
    assert [i["text"] for i in page["open_items"]] == [
        "Ask Sam Lee about wiring", "Send the rota @Sam", "Call Sam about the kiln",
    ]


def test_the_timeline_groups_its_notes_by_month_newest_first(client, session):
    a = _note(session, "Sam Lee came by", datetime(2026, 8, 30, 9))
    b = _note(session, "Sam Lee and the kiln", datetime(2026, 10, 2, 9))
    c = _note(session, "Sam Lee again", datetime(2026, 10, 20, 9))
    hidden = _note(session, "Sam Lee in private", datetime(2026, 7, 1, 9), private=True)
    sam = _entity(session, "Sam Lee", a, b, c, hidden, kind="person")
    timeline = client.get(f"/entities/{sam}").json()["timeline"]
    assert [(m["month"], m["count"]) for m in timeline] == [("2026-10", 2), ("2026-08", 1)]
    assert [n["id"] for n in timeline[0]["notes"]] == [c.id, b.id]


def test_linked_notes_are_the_notes_joined_to_its_notes_that_do_not_name_it(client, session):
    a = _note(session, "Kiln upgrade plan", datetime(2026, 9, 3, 10))
    b = _note(session, "Kiln upgrade budget", datetime(2026, 9, 4, 10))
    wiring = _note(session, "Wiring diagram for the studio", datetime(2026, 9, 5, 10))
    secret = _note(session, "Private quote", datetime(2026, 9, 6, 10), private=True)
    session.add_all([
        EntryLink(source_entry_id=a.id, target_entry_id=wiring.id),
        EntryLink(source_entry_id=wiring.id, target_entry_id=b.id),
        EntryLink(source_entry_id=a.id, target_entry_id=b.id),
        EntryLink(source_entry_id=a.id, target_entry_id=secret.id),
    ])
    kiln = _entity(session, "Kiln upgrade", a, b, kind="project")
    links = client.get(f"/entities/{kiln}").json()["links"]
    assert [(n["id"], n["links"]) for n in links] == [(wiring.id, 2)]
    assert links[0]["title"].startswith("Wiring diagram")


def test_a_notes_connections_list_the_names_it_says(client, session):
    note = _note(session, "Sam Lee and the kiln upgrade", datetime(2026, 9, 3, 10))
    sam = _entity(session, "Sam Lee", note, kind="person")
    kiln = _entity(session, "Kiln upgrade", note, kind="project")
    gone = _entity(session, "Sam", note)
    session.get(Entity, gone).merged_into = sam
    session.commit()
    names = client.get(f"/entries/{note.id}/connections").json()["names"]
    assert [(n["id"], n["kind"]) for n in names] == [(kiln, "project"), (sam, "person")]


def test_a_private_note_lists_no_names(client, session):
    note = _note(session, "Sam Lee in private", datetime(2026, 9, 3, 10), private=True)
    _entity(session, "Sam Lee", note, kind="person")
    assert client.get(f"/entries/{note.id}/connections").json()["names"] == []


def test_the_page_draws_open_items_timeline_and_links_and_connections_open_it():
    js = app_js_text()
    page = js[js.index("async function openEntityPage(") :]
    page = page[: page.index("function entitySection(")]
    for words in ('"Open items"', '"Timeline"', '"Linked notes"'):
        assert words in page, words
    connections = js[js.index("function buildConnectionGroups(") :]
    connections = connections[: connections.index("\n}\n")]
    assert "data.names" in connections and "openEntityPage(" in connections
