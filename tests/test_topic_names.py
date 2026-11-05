"""A topic renamed by hand keeps its name (INBOX 547).

Topics are recomputed from the links, so they have no lasting id; a stored
name is matched to a topic by its notes (half the union shared) and follows
it through a note or two gained or lost. Clearing the name brings the found
one back.
"""

from __future__ import annotations

from tessellate.entry import topics


def _topic(tid, ids, name):
    return {"id": tid, "size": len(ids), "name": name, "terms": [], "ids": ids, "core_id": ids[0]}


def test_a_stored_name_follows_its_topic_through_a_small_change():
    found = [_topic(0, [1, 2, 3, 4, 5], "#glaze"), _topic(1, [6, 7, 8], "#garden")]
    stored = [{"ids": [1, 2, 3, 4], "name": "Pottery"}]
    out = topics.apply_names(found, stored)
    assert out[0]["name"] == "Pottery" and out[0]["named"] and out[0]["found_name"] == "#glaze"
    assert out[1]["name"] == "#garden" and "named" not in out[1]
    assert found[0]["name"] == "#glaze", "the cached value is not changed"


def test_a_name_does_not_jump_to_a_different_topic():
    found = [_topic(0, [1, 2, 3, 9, 10, 11, 12], "#glaze")]
    assert topics.apply_names(found, [{"ids": [1, 2, 3], "name": "Pottery"}])[0]["name"] == "#glaze"


def test_one_stored_name_names_one_topic_best_match_first():
    found = [_topic(0, [1, 2, 3, 4], "a"), _topic(1, [1, 2, 3, 4, 5, 6], "b")]
    out = topics.apply_names(found, [{"ids": [1, 2, 3, 4], "name": "Pottery"}])
    assert [t["name"] for t in out] == ["Pottery", "b"]


def test_store_name_replaces_and_clears():
    stored = topics.store_name([], [1, 2, 3], "Pottery")
    stored = topics.store_name(stored, [1, 2, 3, 4], "Ceramics")
    assert stored == [{"ids": [1, 2, 3, 4], "name": "Ceramics"}]
    assert topics.store_name(stored, [1, 2, 3, 4], "") == []


def _note(client, content, tags=()):
    response = client.post("/entries", json={"content": content, "tags": list(tags)})
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_rename_through_the_api_shows_at_once_and_clears(client):
    notes = [_note(client, f"Glaze test {i}", ["glazing"]) for i in range(4)]
    for i, a in enumerate(notes):
        for b in notes[i + 1 :]:
            client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    ids = [n["id"] for n in notes]
    found = client.get("/graph/structure?topics=1").json()["topics"][0]["name"]
    response = client.put("/graph/topics/name", json={"ids": ids, "name": "  My   pottery "})
    assert response.status_code == 200 and response.json() == {"name": "My pottery"}
    topic = client.get("/graph/structure?topics=1").json()["topics"][0]
    assert topic["name"] == "My pottery" and topic["found_name"] == found
    client.put("/graph/topics/name", json={"ids": ids, "name": ""})
    assert client.get("/graph/structure?topics=1").json()["topics"][0]["name"] == found


def test_rename_rejects_a_long_name(client):
    assert client.put("/graph/topics/name", json={"ids": [1], "name": "x" * 81}).status_code == 422


def _linked_topic(client, word, n=4):
    notes = [_note(client, f"{word} note {i}", [word]) for i in range(n)]
    for i, a in enumerate(notes):
        for b in notes[i + 1 :]:
            client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    return [n["id"] for n in notes]


def test_a_rename_survives_a_recompute_after_the_notebook_changes(client):
    """The owner, 2026-10-10: "I cant rename a topic??". The name is kept by
    the topic's notes, so a new note joining it (a new fingerprint, so the
    topics are found again from scratch) keeps the name the person gave."""
    ids = _linked_topic(client, "glazing")
    client.put("/graph/topics/name", json={"ids": ids, "name": "Pottery"})
    extra = _note(client, "Another glaze", ["glazing"])
    for other in ids[:3]:
        client.post(f"/entries/{extra['id']}/links", json={"target_id": other})
    topic = client.get("/graph/structure?topics=1").json()["topics"][0]
    assert extra["id"] in topic["ids"], "the recompute took the new note in"
    assert topic["name"] == "Pottery" and topic["named"]


def test_a_note_cards_topic_is_read_in_one_batch(client):
    """`/graph/topics/of`: what a note card's topic chip needs, each note's
    topic named (renames applied); a note in no topic is absent."""
    ids = _linked_topic(client, "glazing")
    alone = _note(client, "On its own")
    client.put("/graph/topics/name", json={"ids": ids, "name": "Pottery"})
    body = client.get(f"/graph/topics/of?ids={ids[0]},{ids[1]},{alone['id']},x").json()["topics"]
    assert set(body) == {str(ids[0]), str(ids[1])}
    assert body[str(ids[0])]["name"] == "Pottery" and body[str(ids[0])]["size"] == 4
    assert "ids" not in body[str(ids[0])]
    #: The words that named it, for the chip's hover (INBOX 1620).
    assert "glazing" in [t.lower() for t in body[str(ids[0])]["terms"]]
    full = client.get(f"/graph/topics/of?ids={ids[0]}&members=1").json()["topics"]
    assert sorted(full[str(ids[0])]["ids"]) == sorted(ids)
    empty = client.get("/graph/topics/of").json()
    assert empty == {"topics": {}}


def test_pins_are_written_together(client):
    """A topic dragged as a group pins every member in one request."""
    a, b = _note(client, "pin a"), _note(client, "pin b")
    response = client.put("/graph/pins", json={"pins": [{"id": a["id"], "x": 1.5, "y": 2}, {"id": b["id"], "x": -3, "y": 4}]})
    assert response.status_code == 200 and response.json() == {"pinned": 2}
    nodes = {n["id"]: n for n in client.get("/graph").json()["nodes"]}
    assert (nodes[a["id"]]["graph_pin_x"], nodes[a["id"]]["graph_pin_y"]) == (1.5, 2)
    assert (nodes[b["id"]]["graph_pin_x"], nodes[b["id"]]["graph_pin_y"]) == (-3, 4)
    half = client.put("/graph/pins", json={"pins": [{"id": a["id"], "x": 1, "y": None}]})
    assert half.status_code == 422
