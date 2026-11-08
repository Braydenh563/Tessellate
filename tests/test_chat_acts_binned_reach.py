"""Owner review of the chat acts (restore from the bin, the private-tag hold):
each test failed before its fix. The clock is fixed; binned notes are inserted
straight into the table so a few hundred cost nothing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from tessellate.ai import object_acts
from tessellate.core.database import Entry

NOW = datetime(2026, 11, 8, 10, 0)


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)


def _bin_old_then_many_newer(session, old_content: str, *, count: int = 520) -> int:
    """One note binned long ago, then `count` binned after it."""
    old = Entry(content=old_content, is_deleted=True, deleted_at=NOW - timedelta(days=300))
    session.add(old)
    session.flush()
    session.add_all(
        Entry(content=f"# Filler {i}\n\nx", is_deleted=True, deleted_at=NOW - timedelta(days=1, minutes=i))
        for i in range(count)
    )
    session.commit()
    return old.id


def _card(client, said):
    with client.stream("POST", "/chat/stream", json={"question": said, "use_tools": True}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line.strip()]
    return next((e for e in events if e.get("type") == "act"), None), events


def test_restore_by_number_reaches_a_note_older_than_the_newest_500(client, session):
    old = _bin_old_then_many_newer(session, "# Passport\n\nRenew it.")
    card, _ = _card(client, f"restore note {old}")
    assert card and card["steps"][0]["arguments"]["note_id"] == old


def test_restore_by_words_reaches_a_note_older_than_the_newest_500(client, session):
    old = _bin_old_then_many_newer(session, "# Passport\n\nRenew it.")
    card, _ = _card(client, "restore the passport note")
    assert card and card["steps"][0]["arguments"]["note_id"] == old


def test_a_word_with_an_underscore_is_matched_literally(session):
    snake = Entry(content="# snake_case rules", is_deleted=True, deleted_at=NOW)
    other = Entry(content="# snakeXcase rules", is_deleted=True, deleted_at=NOW)
    session.add_all([snake, other])
    session.commit()
    found = object_acts._binned(session, {"about": "snake_case"})
    assert [row.id for row in found] == [snake.id]


def test_an_accented_word_is_still_found_beyond_ascii_case_folding(session):
    note = Entry(content="# Équipe plan", is_deleted=True, deleted_at=NOW)
    session.add(note)
    session.commit()
    assert [row.id for row in object_acts._binned(session, {"about": "équipe"})] == [note.id]


def test_the_private_hold_reads_the_tags_column_only(session, monkeypatch):
    from tessellate.core import vault

    monkeypatch.setattr(vault, "key", lambda: None)
    session.add(Entry(content="# Secret body", is_private=True, tags=json.dumps(["gym"])))
    session.add(Entry(content="# Open", tags=json.dumps(["gym"])))
    session.commit()
    seen: list[str] = []

    def spy(conn, cursor, statement, *rest):
        seen.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", spy)
    try:
        assert object_acts._private_hold(session, "gym") is True
        assert object_acts._private_hold(session, "other") is False
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    selects = [s for s in seen if s.lstrip().upper().startswith("SELECT") and "is_private" in s.lower()]
    assert selects, seen
    for statement in selects:
        assert "content" not in statement.lower().split(" from ")[0], statement
