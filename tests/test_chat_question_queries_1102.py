"""A chat question's database work is a fixed number of queries, whatever the
pool's size (2026-11-02 sweep: 329 for a 24-note answer).

Counting every note it surfaced as used rewrote each note's search-index row
(72 deletes and 24 inserts: `access_count` is read by no row), and each pool
row and prompt row looked up its category, dates, documents, links and
attachments one note at a time."""

from __future__ import annotations

from sqlalchemy import event

from tessellate.entry import manager


def _ask(client, question: str) -> None:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        for _ in response.iter_lines():
            pass


def _statements(client, session, question: str, with_params: bool = False) -> list:
    said: list = []
    engine = session.get_bind()

    def hook(conn, cursor, statement, params, context, many):  # noqa: ANN001, ARG001
        said.append((statement, params) if with_params else statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        _ask(client, question)
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return said


def _notes(session, n: int) -> None:
    for i in range(n):
        manager.create_entry(session, f"# Run {i}\n\nRunning plan week {i}: three runs, 5 km each.\n")
    session.commit()


def test_counting_notes_as_used_writes_no_index_rows(client, session):
    _notes(session, 30)
    _ask(client, "hello")
    said = _statements(client, session, "what do I know about running", with_params=True)
    inserts = [p for s, p in said if s.lstrip().upper().startswith("INSERT INTO SEARCH_INDEX")]
    deletes = [s for s, _ in said if s.lstrip().upper().startswith("DELETE FROM SEARCH_INDEX")]
    #: The chat itself is saved and searchable: its one row is the only write.
    assert len(inserts) <= 1 and len(deletes) <= 1, (len(inserts), len(deletes))
    assert all(p[1] == "what do I know about running" for p in inserts), inserts  # the chat's own row


def test_a_pool_is_read_in_a_fixed_number_of_queries(client, session):
    _notes(session, 30)
    _ask(client, "hello")
    per_note = ("FROM entry_dates", "FROM documents", "FROM entry_links", "FROM attachments", "FROM categories")
    said = _statements(client, session, "what do I know about running")
    counts = {t: sum(1 for s in said if t in s) for t in per_note}
    assert all(n <= 8 for n in counts.values()), counts
