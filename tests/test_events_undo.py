"""Undo what one actor did (OPEN.md, "Global undo of an AI action", `events-undo`).

"`replay` and `restore` cover one note; 'undo auto-filing' means selecting
the events of one actor in one window and applying each `before` in
reverse. Next step: `events.undo(session, actor, since_id)` ... It has to
refuse an event whose values are gone (`events.is_compacted`)."

What must hold:

- only the named actor's changes, only after `since_id`, are undone;
- a note the person changed after the AI did is left alone and said so,
  unless the caller forces it (the person's edit wins by default);
- undoing twice does nothing the second time;
- a note the AI created goes to the recycle bin (recoverable), not away;
- a compacted event, a board item, and a privacy change are refused by name;
- the dry run changes nothing and returns the same plan the real run acts on.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from tessellate.core import events, events_redo
from tessellate.core.database import AuditLog, Entry
from tessellate.entry import manager

AI = "system:librarian"


def _note(session, content="The pond needs a pump before spring", tags=("garden",)) -> Entry:
    entry = manager.create_entry(session, content, category_name="Garden", tags=list(tags))
    session.commit()
    return entry


def _as_ai(session, entry: Entry, **changes) -> None:
    with events.acting_as(AI):
        manager.update_entry(session, entry, **changes)
    session.commit()


def _last_event_id(session) -> int:
    return session.scalar(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)) or 0


def test_an_ai_refile_and_retag_is_put_back(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies", tags=["pond", "pump"])
    assert manager.category_name_for(session, entry) == "Hobbies"

    plan = events.undo(session, AI, since_id=mark, apply=False)
    assert [(item["entity_id"], item["status"]) for item in plan["items"]] == [(entry.id, "undo")]
    assert manager.category_name_for(session, entry) == "Hobbies"  # a dry run changes nothing

    done = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(entry)
    assert done["undone"] == 1
    assert manager.category_name_for(session, entry) == "Garden"
    assert json.loads(entry.tags) == ["garden"]
    restored = session.scalars(
        select(AuditLog).where(AuditLog.entity_id == entry.id, AuditLog.action == "restored")
    ).all()
    assert len(restored) == 1 and restored[0].actor == events.ACTOR_USER
    assert AI in (restored[0].detail or "")


def test_undoing_twice_does_nothing_the_second_time(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    again = events.undo(session, AI, since_id=mark, apply=True)
    assert again["undone"] == 0
    assert [item["status"] for item in again["items"]] == ["already undone"]


def test_the_persons_later_edit_wins_unless_forced(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    manager.update_entry(session, entry, content="The pond needs a pump and a net")
    session.commit()
    plan = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    assert [item["status"] for item in plan["items"]] == ["changed since"]
    assert manager.category_name_for(session, entry) == "Hobbies"
    forced = events.undo(session, AI, since_id=mark, apply=True, force=True)
    session.commit()
    session.refresh(entry)
    assert forced["undone"] == 1
    assert manager.category_name_for(session, entry) == "Garden"
    # Only the fields the AI changed go back: the person's text stays.
    assert entry.content == "The pond needs a pump and a net"


def test_only_the_named_actor_and_only_after_the_mark(session):
    entry = _note(session)
    _as_ai(session, entry, category_name="Hobbies")  # before the mark
    mark = _last_event_id(session)
    _as_ai(session, entry, tags=["pond"])
    other = _note(session, "Buy a new bike chain", tags=())
    with events.acting_as("ai:tidy"):
        manager.update_entry(session, other, category_name="Errands")
    session.commit()
    events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(entry)
    session.refresh(other)
    assert json.loads(entry.tags) == ["garden"]
    assert manager.category_name_for(session, entry) == "Hobbies"  # before the mark: kept
    assert manager.category_name_for(session, other) == "Errands"  # another actor: kept


def test_a_note_the_ai_made_goes_to_the_bin(session):
    mark = _last_event_id(session)
    with events.acting_as(AI):
        made = manager.create_entry(session, "A draft the librarian captured from chat")
    session.commit()
    done = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(made)
    assert done["undone"] == 1
    assert made.is_deleted is True  # recoverable from the bin, not purged


def test_what_cannot_be_undone_is_named(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    row = session.scalars(
        select(AuditLog).where(AuditLog.actor == AI, AuditLog.entity_id == entry.id)
    ).first()
    row.payload = {events.COMPACTED: True}
    events.record(session, "edited", "node", 7, payload={"before": {"x": 1}, "after": {"x": 2}}, actor=AI)
    session.commit()
    plan = events.undo(session, AI, since_id=mark, apply=False)
    by_type = {item["entity_type"]: item["status"] for item in plan["items"]}
    assert by_type == {"entry": "too old", "node": "not undoable"}


def test_the_route_is_a_dry_run_unless_told(client, session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    preview = client.post("/events/undo", json={"actor": AI, "since": mark}).json()
    assert preview["dry_run"] is True and preview["items"][0]["status"] == "undo"
    session.refresh(entry)
    assert manager.category_name_for(session, entry) == "Hobbies"
    applied = client.post("/events/undo", json={"actor": AI, "since": mark, "dry_run": False}).json()
    assert applied["undone"] == 1
    session.expire_all()
    assert manager.category_name_for(session, session.get(Entry, entry.id)) == "Garden"


def test_the_person_is_not_an_actor_to_undo(client):
    response = client.post("/events/undo", json={"actor": "user", "since": 0})
    assert response.status_code == 400


# --- the auto-filer's own moves are events it owns ---------------------------------
#
# Found while building the above: the three places the AI files a note
# (capture's background filing, adding context, re-evaluation) either wrote no
# event at all or an `edited` event with no values, attributed to the person.
# So "undo auto-filing" had nothing to find, and a note's History could not
# rebuild the category it had between capture and now.


def _pick(category: str, method: str = "llm"):
    def categorise(*_args, **_kwargs):
        return category, 90, method

    return categorise


def test_capture_filing_is_an_event_the_filer_owns_and_undo_reverses(client, session, monkeypatch):
    from tessellate.ai import janitor
    from tessellate.api import routes_entries

    entry = manager.create_entry(session, "Repot the fig before it gets root bound")
    entry.filing_state = "pending"  # as a deferred save leaves it
    session.commit()
    mark = _last_event_id(session)
    monkeypatch.setattr(janitor, "categorise", _pick("Garden"))
    routes_entries._file_entry_in_background(entry.id, "default")
    session.expire_all()
    row = session.scalars(
        select(AuditLog).where(AuditLog.entity_id == entry.id, AuditLog.id > mark)
    ).one()
    assert row.actor == manager.FILING_ACTOR
    assert set(row.payload["after"]) == {"category_id"}
    done = client.post(
        "/events/undo", json={"actor": manager.FILING_ACTOR, "since": mark, "dry_run": False}
    ).json()
    assert done["undone"] == 1
    session.expire_all()
    assert manager.category_name_for(session, session.get(Entry, entry.id)) == manager.UNCATEGORISED


def test_a_filing_that_changes_nothing_writes_nothing(session, monkeypatch):
    from tessellate.ai import janitor
    from tessellate.api import routes_entries

    entry = manager.create_entry(session, "Repot the fig", category_name="Garden")
    entry.filing_state = "pending"
    session.commit()
    mark = _last_event_id(session)
    monkeypatch.setattr(janitor, "categorise", _pick("Garden"))
    routes_entries._file_entry_in_background(entry.id, "default")
    session.expire_all()
    assert _last_event_id(session) == mark


def test_reevaluation_files_as_the_filer_with_values(client, session, monkeypatch):
    from tessellate.ai import janitor

    entry = manager.create_entry(session, "Repot the fig before it gets root bound")
    session.commit()
    mark = _last_event_id(session)
    monkeypatch.setattr(janitor, "categorise", _pick("Garden"))
    assert client.post(f"/entries/{entry.id}/reevaluate").status_code == 200
    session.expire_all()
    moves = session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == entry.id,
            AuditLog.id > mark,
            AuditLog.actor == manager.FILING_ACTOR,
        )
    ).all()
    assert len(moves) == 1 and "category_id" in moves[0].payload["before"]


def test_private_text_under_a_rotated_key_is_not_written_back(session, monkeypatch):
    """A payload keeps a private note's column as it was: ciphertext under the
    key of that day. After `rotate-vault-key` that text reads under nothing,
    so writing it back would leave a note nobody can open. The other fields
    still go back; the text stays, and the plan says so."""
    from tessellate.core import crypto, vault

    old_key, new_key = crypto.new_dek(), crypto.new_dek()
    entry = _note(session)
    entry.content = crypto.encrypt(old_key, "before the AI")
    session.commit()
    mark = _last_event_id(session)
    _as_ai(session, entry, tags=["pond"], content=crypto.encrypt(old_key, "after the AI"))
    entry.content = crypto.encrypt(new_key, "after the AI")  # what the rotation writes
    session.commit()
    monkeypatch.setattr(vault, "key", lambda: new_key)

    plan = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(entry)
    assert plan["items"][0]["kept"] == ["content"]
    assert "content" not in plan["items"][0]["fields"]
    assert crypto.decrypt(new_key, entry.content) == "after the AI"
    assert json.loads(entry.tags) == ["garden"]


def test_private_text_under_the_current_key_is_put_back(session, monkeypatch):
    from tessellate.core import crypto, vault

    key = crypto.new_dek()
    entry = _note(session)
    entry.content = crypto.encrypt(key, "before the AI")
    session.commit()
    mark = _last_event_id(session)
    _as_ai(session, entry, content=crypto.encrypt(key, "after the AI"))
    monkeypatch.setattr(vault, "key", lambda: key)

    events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(entry)
    assert crypto.decrypt(key, entry.content) == "before the AI"


def test_a_redo_puts_the_ais_change_back_and_a_second_undo_works_l805(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies", tags=["pond"])
    done = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    assert len(done["restored"]) == 1
    assert manager.category_name_for(session, entry) == "Garden"

    plan = events_redo.redo(session, done["restored"], apply=False)
    assert [item["status"] for item in plan["items"]] == ["redo"]
    assert manager.category_name_for(session, entry) == "Garden"  # a dry run writes nothing

    back = events_redo.redo(session, done["restored"], apply=True)
    session.commit()
    session.refresh(entry)
    assert back["redone"] == 1
    assert manager.category_name_for(session, entry) == "Hobbies"
    assert json.loads(entry.tags) == ["pond"]

    twice = events_redo.redo(session, done["restored"], apply=True)
    assert [item["status"] for item in twice["items"]] == ["already redone"]

    # The redo made the AI's events live again: the same undo runs once more,
    # and the undo/redo pair is not read as the person's edit in between.
    again = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    session.refresh(entry)
    assert again["undone"] == 1
    assert manager.category_name_for(session, entry) == "Garden"


def test_a_redo_leaves_a_note_the_person_changed_since_l805(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    done = events.undo(session, AI, since_id=mark, apply=True)
    manager.update_entry(session, entry, content="Mine now")
    session.commit()
    back = events_redo.redo(session, done["restored"], apply=True)
    assert [item["status"] for item in back["items"]] == ["changed since"]
    assert back["redone"] == 0


def test_the_redo_route_and_the_feed_name_what_it_took_back_l805(client, session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    undone = client.post("/events/undo", json={"actor": AI, "since": mark, "dry_run": False}).json()
    assert undone["undone"] == 1
    redone = client.post("/events/redo", json={"restored": undone["restored"]}).json()
    assert redone["redone"] == 1
    feed = client.get(f"/events?since={mark}&include_quiet=true").json()["items"]
    assert [i["redid"] for i in feed if i["action"] == "redone"] == [undone["restored"]]


def _undone_note(session):
    entry = _note(session)
    mark = _last_event_id(session)
    _as_ai(session, entry, category_name="Hobbies")
    done = events.undo(session, AI, since_id=mark, apply=True)
    session.commit()
    return entry, done["restored"]


def _redone_events(session) -> int:
    return len(session.scalars(select(AuditLog.id).where(AuditLog.action == "redone")).all())


def test_a_redo_leaves_a_binned_or_private_note_alone(session):
    """Review 5899353774 (2): a redo wrote a binned note, and a private one's
    words would land in the `redone` event's `changed` in the clear."""
    binned, binned_ids = _undone_note(session)
    binned.is_deleted = True
    sealed, sealed_ids = _undone_note(session)
    sealed.is_private = True
    session.commit()
    back = events_redo.redo(session, binned_ids + sealed_ids, apply=True)
    assert [item["status"] for item in back["items"]] == ["binned", "private"]
    assert back["redone"] == 0 and _redone_events(session) == 0
    assert manager.category_name_for(session, sealed) == "Garden"


def test_two_redos_at_once_apply_once(session):
    """Review 5899353774 (1): both read "not yet redone" before either wrote."""
    import threading

    from sqlalchemy.orm import Session as OrmSession

    _, restored = _undone_note(session)
    bind = session.get_bind()
    gate = threading.Barrier(2)
    results = []

    def press():
        with OrmSession(bind) as own:
            gate.wait()
            results.append(events_redo.redo(own, restored, apply=True)["redone"])

    threads = [threading.Thread(target=press) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(results) == [0, 1]
    session.expire_all()
    assert _redone_events(session) == 1


def test_a_redo_reads_the_later_edits_in_one_query_whatever_the_count(session):
    """Review 5899353774 (3): one query per `restored` row became one in all."""
    from sqlalchemy import event

    restored = []
    for _ in range(3):
        restored += _undone_note(session)[1]
    seen = []

    def count(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT") and "audit_log" in statement.lower():
            seen.append(statement)

    engine = session.get_bind()
    counts = []
    for ids in (restored[:1], restored):
        seen.clear()
        event.listen(engine, "before_cursor_execute", count)
        try:
            events_redo.redo(session, ids, apply=False)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        counts.append(len(seen))
    assert counts[0] == counts[1]
