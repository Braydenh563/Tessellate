"""K36 (audit 1028 backend): the board list's cost does not grow per board.

Each board's thumbnail fingerprint was five aggregate queries run once per
board in the page. They are now grouped over the whole page, so the number of
statements for `GET /whiteboard/boards` is the same for 3 boards and for 12.
Counted, not timed, so a regression fails on any machine.
"""

from __future__ import annotations

from sqlalchemy import event

from tessellate.core import deps


def _make_boards(client, count):
    for n in range(count):
        made = client.post("/whiteboard/boards", json={"name": f"K36 board {n}", "type": "map", "layout": "tree-right"})
        assert made.status_code == 201, made.text
        node = client.post(f"/whiteboard/boards/{made.json()['id']}/nodes", json={"kind": "topic", "parent_id": None, "text": f"Root {n}"})
        assert node.status_code == 201, node.text


def _statements(client) -> int:
    engine = deps.get_db().engine
    seen: list[str] = []
    #: A first listing fills the thumbnail cache (a miss draws the board, which
    #: is its own cost); the count is of the listing after it.
    assert client.get("/whiteboard/boards").status_code == 200

    def count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        listed = client.get("/whiteboard/boards")
        assert listed.status_code == 200, listed.text
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return len(seen)


def test_the_board_list_statement_count_does_not_grow_with_the_boards(client):
    _make_boards(client, 3)
    few = _statements(client)
    _make_boards(client, 9)
    many = _statements(client)
    assert many == few, f"{few} statements for 3 boards, {many} for 12"


def test_the_thumbnail_still_follows_a_board_edit(client):
    """The grouped fingerprint must still change when the board does."""
    _make_boards(client, 2)
    before = {b["id"]: b["preview_items"] for b in client.get("/whiteboard/boards").json() if b["id"]}
    target = next(iter(before))
    added = client.post(f"/whiteboard/boards/{target}/nodes", json={"kind": "topic", "parent_id": None, "text": "Another"})
    assert added.status_code == 201, added.text
    after = {b["id"]: b["preview_items"] for b in client.get("/whiteboard/boards").json() if b["id"]}
    assert len(after[target]) == len(before[target]) + 1
    other = next(i for i in before if i != target)
    assert after[other] == before[other]
