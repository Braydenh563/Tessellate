"""A chat question counts the notes it surfaced as used without moving their `updated_at`.

`Entry.updated_at` has `onupdate=utcnow`, so counting a note as used moved it, and every question
then invalidated what is keyed on the notebook's newest edit (the abbreviation glossary re-read
every note: audit-1108-perf P6, W30 D28). The count is one UPDATE that names `updated_at`."""

from __future__ import annotations

from sqlalchemy import event

from tessellate.api import chat_pool
from tessellate.core.database import Entry
from tessellate.entry import manager


def _ask(client, question: str) -> None:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        for _ in response.iter_lines():
            pass


def test_a_question_counts_notes_as_used_and_leaves_their_edit_time(client, session):
    ids = [manager.create_entry(session, f"# Run {i}\n\nRunning plan week {i}: three runs.\n").id for i in range(6)]
    session.commit()
    before = {i: session.get(Entry, i).updated_at for i in ids}
    counted_before = {i: session.get(Entry, i).access_count for i in ids}
    _ask(client, "what do I know about running")
    session.expire_all()
    after = {i: session.get(Entry, i).updated_at for i in ids}
    counted_after = {i: session.get(Entry, i).access_count for i in ids}
    assert after == before, "reading is not editing"
    assert any(counted_after[i] > counted_before[i] for i in ids), "the surfaced notes are still counted"


def test_the_glossary_key_survives_a_question(client, session):
    for i in range(4):
        manager.create_entry(session, f"# Run {i}\n\nRunning plan week {i}.\n")
    session.commit()
    _ask(client, "what do I know about running")
    chat_pool._glossary(session)
    held = chat_pool._GLOSSARY["key"]
    _ask(client, "what do I know about running")
    chat_pool._glossary(session)
    assert chat_pool._GLOSSARY["key"] == held


def test_counting_notes_as_used_is_one_statement(client, session):
    for i in range(12):
        manager.create_entry(session, f"# Run {i}\n\nRunning plan week {i}: three runs.\n")
    session.commit()
    _ask(client, "hello")
    said: list[str] = []
    engine = session.get_bind()

    def hook(conn, cursor, statement, params, context, many):  # noqa: ANN001, ARG001
        said.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        _ask(client, "what do I know about running")
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    counting = [s for s in said if s.lstrip().upper().startswith("UPDATE ENTRIES") and "access_count" in s]
    assert len(counting) <= 1, counting
