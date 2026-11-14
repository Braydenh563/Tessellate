"""WORLD_CLASS_PLAN D5's last two parts: the built-in kinds and the graph
colouring by them.

KG4 (GRAPH_PLAN, 2026-10-04) built typed properties on notes and user-made
note types; D5's gate also asked for built-in kinds (person, project,
meeting, book, place) and "the graph colours by it". A notebook seeds the five
once, and never again after a person deletes them; the graph carries each
note's type and the type's own colour.
"""

from __future__ import annotations

BUILT_IN = {"Person", "Project", "Meeting", "Book", "Place"}


def test_a_fresh_notebook_has_the_five_kinds_each_with_a_colour_and_fields(client):
    rows = client.get("/note-types").json()
    names = {row["name"] for row in rows}
    assert BUILT_IN <= names
    for row in rows:
        if row["name"] in BUILT_IN:
            assert row["colour"] and row["colour"].startswith("#"), row
            assert row["icon"], row
            assert row["fields"], row


def test_the_kinds_are_seeded_once_and_a_deleted_one_stays_deleted(client):
    rows = client.get("/note-types").json()
    for row in rows:
        response = client.delete(f"/note-types/{row['id']}")
        assert response.status_code == 200
    assert client.get("/note-types").json() == []


def test_the_graph_colours_by_note_type(client):
    client.get("/note-types")
    made = client.post("/entries", json={"content": "Ada Lovelace", "note_type": "Person"}).json()
    plain = client.post("/entries", json={"content": "A plain thought"}).json()
    graph = client.get("/graph").json()
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert nodes[made["id"]]["note_type"] == "Person"
    assert nodes[plain["id"]]["note_type"] is None
    assert graph["type_colours"]["Person"].startswith("#")


def test_search_finds_a_note_by_a_property_value(client):
    client.post("/entries", json={"content": "---\nauthor: Ursula Leguin\n---\n# Earthsea\n\nA wizard."})
    body = client.get("/search", params={"q": "Leguin"}).json()
    assert body["hits"], body


def test_the_graph_offers_the_type_rule():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    graph = (root / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    canvas = (root / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert '<option value="type">Note type</option>' in html
    assert '"type"' in graph.split("const GRAPH_COLOUR_RULES", 1)[1].split("\n", 1)[0]
    assert 'rule === "type"' in canvas


# Undo for a deleted note type: it comes back with its id and fields


def test_a_deleted_note_type_comes_back_with_its_id_and_fields(client):
    #: The types panel lists before it makes, which seeds the five built-in
    #: types (Person, Project, Meeting, Book, Place) once; seeding after the
    #: delete would hand the deleted id to Person.
    seeded = {t["id"] for t in client.get("/note-types").json()}
    made = client.post(
        "/note-types",
        json={"name": "Standup", "icon": "ph-users", "colour": "teal", "fields": [{"name": "attendees", "kind": "list"}]},
    ).json()
    gone = client.delete(f"/note-types/{made['id']}").json()
    assert gone["type"] == made
    assert {t["id"] for t in client.get("/note-types").json()} == seeded
    back = client.post("/note-types", json={**gone["type"], "restore": True})
    assert back.status_code == 201, back.text
    assert back.json() == made
    # Without `restore` an id in the body is ignored, as before.
    other = client.post("/note-types", json={"name": "Other", "id": 999}).json()
    assert other["id"] != 999


def test_a_note_type_made_before_the_list_was_read_keeps_its_id_through_delete_and_undo(client):
    """A type made by POST /note-types before the types list was ever read
    keeps its id through delete and Undo. The list's first read seeds the
    built-in types, so the list holds them too; only the two made here are
    pinned. The last case (integ-1005, L571) has its own test below."""
    first = client.post("/note-types", json={"name": "Meeting log"}).json()
    second = client.post("/note-types", json={"name": "Reading list"}).json()
    gone = client.delete(f"/note-types/{first['id']}").json()
    back = client.post("/note-types", json={**gone["type"], "restore": True})
    assert back.status_code == 201, back.text
    assert back.json()["id"] == first["id"]
    ids = {t["id"] for t in client.get("/note-types").json()}
    assert {first["id"], second["id"]} <= ids


def test_the_only_type_deleted_then_the_list_read_still_gets_its_id_back(client):
    """L571 (integ-1005): the only type made, deleted, then the list read
    before Undo. The list's first read seeded the built-ins into the freed
    id, so Undo gave the type a new one; the seed now runs on create too."""
    only = client.post("/note-types", json={"name": "Meeting log"}).json()
    gone = client.delete(f"/note-types/{only['id']}").json()
    assert client.get("/note-types").status_code == 200
    back = client.post("/note-types", json={**gone["type"], "restore": True})
    assert back.status_code == 201, back.text
    assert back.json()["id"] == only["id"]
