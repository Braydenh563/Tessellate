"""`/graph` serves its encoded payload from a cache while nothing in it moved.

GRAPH_PLAN "Still open after KG1 to KG9": at 5,000 notes the payload was 0.7
to 1.0 s warm and 3 MB, rebuilt on every visit. The cache's key has to cover
what moves a node without editing a note (pins, access counts, attachments,
board members, the vault), or the map would show yesterday's picture; each
test below moves one of them and expects a fresh build.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_graph
from tessellate.core import deps
from tessellate.core.database import Attachment, Entry, WhiteboardObject


@pytest.fixture()
def builds(monkeypatch):
    calls = []
    real = routes_graph._build_graph

    def counting(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(routes_graph, "_build_graph", counting)
    return calls


def _node(client, entry_id):  # noqa: ANN001, ANN202
    return next(n for n in client.get("/graph").json()["nodes"] if n["id"] == entry_id)


def test_a_second_visit_is_served_without_a_build(client, builds):
    client.post("/entries", json={"content": "one note"})
    first = client.get("/graph").content
    second = client.get("/graph").content
    assert first == second
    assert len(builds) == 1


def test_an_edit_rebuilds(client, builds):
    note = client.post("/entries", json={"content": "one note"}).json()
    client.get("/graph")
    client.put(f"/entries/{note['id']}", json={"content": "one note, edited"})
    assert _node(client, note["id"])["preview"].startswith("one note, edited")
    assert len(builds) == 2


def test_a_pin_rebuilds(client, builds):
    note = client.post("/entries", json={"content": "one note"}).json()
    client.get("/graph")
    with deps.get_db().session() as session:
        row = session.get(Entry, note["id"])
        row.graph_pin_x, row.graph_pin_y = 10.0, 20.0
        session.commit()
    assert _node(client, note["id"])["graph_pin_x"] == 10.0


def test_an_access_count_rebuilds(client, builds):
    note = client.post("/entries", json={"content": "one note"}).json()
    client.get("/graph")
    with deps.get_db().session() as session:
        session.get(Entry, note["id"]).access_count = 7
        session.commit()
    assert _node(client, note["id"])["access_count"] == 7


def test_an_attachment_rebuilds(client, builds):
    note = client.post("/entries", json={"content": "one note"}).json()
    assert _node(client, note["id"])["has_file"] is False
    with deps.get_db().session() as session:
        session.add(Attachment(entry_id=note["id"], filename="a.txt", stored_name="perf2-a.txt"))
        session.commit()
    assert _node(client, note["id"])["has_file"] is True


def test_a_note_put_on_a_map_rebuilds(client, builds):
    note = client.post("/entries", json={"content": "one note"}).json()
    board = client.post("/whiteboard/boards", json={"name": "A map", "type": "map"}).json()
    assert _node(client, note["id"])["map_ids"] == []
    with deps.get_db().session() as session:
        session.add(WhiteboardObject(board_id=board["id"], kind="note", data='{"ref_id": %d}' % note["id"]))
        session.commit()
    assert _node(client, note["id"])["map_ids"] == [board["id"]]


def test_the_opt_in_layers_the_key_does_not_cover_are_built_every_time(client, builds):
    client.post("/entries", json={"content": "one note"})
    client.get("/graph?include_entities=true")
    client.get("/graph?include_entities=true")
    assert len(builds) == 2


def test_locking_the_vault_rebuilds_a_private_notes_label(client, session, builds):
    """The key carries whether this request may read private text: the same
    notebook locked and unlocked is two payloads."""
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    try:
        note = client.post("/entries", json={"content": "the spare key is under the mat"}).json()
        assert client.post(f"/entries/{note['id']}/privacy", json={"private": True}).status_code == 200
        assert _node(client, note["id"])["preview"].startswith("the spare key")
        vault.close()
        # INBOX 1437: a sealed node is titled "Private note", no longer the
        # read placeholder; the point here (a lock rebuilds the label) is unchanged.
        assert _node(client, note["id"])["preview"] == "Private note"
    finally:
        vault.close()
