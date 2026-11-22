"""L613: a note type that was the only one, deleted, then the list read (which
seeds the built-in types), then Undo: it comes back with its own id, and the
seeded types keep theirs."""

from __future__ import annotations


def test_the_only_type_deleted_then_the_list_read_then_undo_keeps_its_id(client):
    made = client.post("/note-types", json={"name": "Meeting log"}).json()
    gone = client.delete(f"/note-types/{made['id']}").json()
    seeded = client.get("/note-types").json()
    assert all(t["id"] != made["id"] for t in seeded), "a seeded type took the deleted id"
    back = client.post("/note-types", json={**gone["type"], "restore": True})
    assert back.status_code == 201, back.text
    assert back.json()["id"] == made["id"]
    after = {t["id"]: t["name"] for t in client.get("/note-types").json()}
    assert after[made["id"]] == "Meeting log"
    assert {t["id"] for t in seeded} <= set(after)


def test_a_type_made_after_a_delete_does_not_take_the_deleted_id(client):
    client.get("/note-types")
    made = client.post("/note-types", json={"name": "Meeting log"}).json()
    gone = client.delete(f"/note-types/{made['id']}").json()
    other = client.post("/note-types", json={"name": "Reading list"}).json()
    assert other["id"] != made["id"]
    back = client.post("/note-types", json={**gone["type"], "restore": True}).json()
    assert back["id"] == made["id"]
