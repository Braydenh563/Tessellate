"""Expand from my notes (MINDMAP_PLAN 12.3 item 2, the features audit Phase G).

A topic that IS a note is grown one level from that note itself: its headings
and the notes it links to, with no search and no model, so nothing here needs a
fake transport. Preview writes nothing; the ticked ones are added through the
same `/branches` route Branches from my notes uses.
"""

from __future__ import annotations

NOTE = (
    "# Tomato pruning\n\nIntro text.\n\n## Side shoots\n\npinch them\n\n"
    "## Watering\n\nmorning\n\n### Drip lines\n\nsmall\n\n```\n# not a heading\n```\n"
)


def _note(client, content):
    return client.post("/entries", json={"content": content}).json()


def _map_with_note_topic(client, note):
    board = client.post("/whiteboard/boards", json={"name": "Garden map", "type": "map"}).json()
    node = client.post(
        f"/whiteboard/boards/{board['id']}/nodes", json={"kind": "note", "ref_id": note["id"]}
    ).json()
    return board["id"], node["id"]


def test_headings_become_suggestions_and_the_title_heading_does_not(client):
    note = _note(client, NOTE)
    bid, nid = _map_with_note_topic(client, note)
    before = len(client.get("/whiteboard/", params={"board_id": bid}).json()["objects"])
    out = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand")
    assert out.status_code == 200, out.text
    got = out.json()
    assert got["topic"] == "Tomato pruning" and got["source"] == "note"
    assert [(s["text"], s["kind"]) for s in got["suggestions"]] == [
        ("Side shoots", "heading"),
        ("Watering", "heading"),
        ("Drip lines", "heading"),
    ]
    assert all(s["note_id"] == note["id"] and s["note_title"] == "Tomato pruning" for s in got["suggestions"])
    assert len(client.get("/whiteboard/", params={"board_id": bid}).json()["objects"]) == before


def test_linked_notes_follow_the_headings_and_name_themselves(client):
    note = _note(client, NOTE)
    other = _note(client, "# Compost heap\n\nturn it weekly")
    inbound = _note(client, "# Seed catalogue\n\nsee tomatoes")
    client.post(f"/entries/{note['id']}/links", json={"target_id": other["id"]})
    client.post(f"/entries/{inbound['id']}/links", json={"target_id": note["id"]})
    bid, nid = _map_with_note_topic(client, note)
    got = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    kinds = [s["kind"] for s in got["suggestions"]]
    assert kinds == ["heading"] * 3 + ["link"] * 2
    links = {s["text"]: s for s in got["suggestions"] if s["kind"] == "link"}
    assert set(links) == {"Compost heap", "Seed catalogue"}
    assert links["Compost heap"]["note_id"] == other["id"] and links["Compost heap"]["note_title"] == "Compost heap"


def test_children_already_there_and_notes_already_on_the_map_are_left_out(client):
    note = _note(client, NOTE)
    other = _note(client, "# Compost heap\n\nturn it weekly")
    client.post(f"/entries/{note['id']}/links", json={"target_id": other["id"]})
    bid, nid = _map_with_note_topic(client, note)
    client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "topic", "text": "side shoots", "parent_id": nid})
    client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "note", "ref_id": other["id"]})
    got = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    assert [s["text"] for s in got["suggestions"]] == ["Watering", "Drip lines"]


def test_a_deleted_linked_note_is_never_offered(client):
    note = _note(client, NOTE)
    gone = _note(client, "# Old plan\n\nx")
    client.post(f"/entries/{note['id']}/links", json={"target_id": gone["id"]})
    client.delete(f"/entries/{gone['id']}")
    bid, nid = _map_with_note_topic(client, note)
    got = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    assert "Old plan" not in {s["text"] for s in got["suggestions"]}


def test_a_note_with_nothing_to_expand_says_so(client):
    note = _note(client, "# Lonely\n\njust a line")
    bid, nid = _map_with_note_topic(client, note)
    got = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    assert got["suggestions"] == [] and got["reason"] == "nothing"


def test_a_plain_topic_or_another_maps_topic_is_refused(client):
    note = _note(client, NOTE)
    bid, nid = _map_with_note_topic(client, note)
    plain = client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "topic", "text": "Gardening"}).json()
    refused = client.post(f"/whiteboard/boards/{bid}/nodes/{plain['id']}/expand")
    assert refused.status_code == 422
    assert "Branches from my notes" in refused.json()["detail"]
    other, _ = _map_with_note_topic(client, note)
    elsewhere = client.post(f"/whiteboard/boards/{other}/nodes/{nid}/expand")
    assert elsewhere.status_code == 404


def test_a_document_topic_is_refused_not_read_as_the_note_with_that_id(client):
    _note(client, NOTE)
    doc = client.post("/documents", json={"title": "Plan", "content": "# Plan\n\n## Step one"}).json()
    board = client.post("/whiteboard/boards", json={"name": "Docs map", "type": "map"}).json()
    node = client.post(
        f"/whiteboard/boards/{board['id']}/nodes", json={"kind": "document", "ref_id": doc["id"]}
    ).json()
    out = client.post(f"/whiteboard/boards/{board['id']}/nodes/{node['id']}/expand")
    assert out.status_code == 422


def test_the_ticked_ones_are_added_through_the_branches_route(client):
    note = _note(client, NOTE)
    bid, nid = _map_with_note_topic(client, note)
    got = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    items = [{"text": s["text"], "note_id": s["note_id"]} for s in got["suggestions"][:2]]
    made = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/branches", json={"items": items}).json()
    assert [m["data"]["content"] for m in made] == ["Side shoots", "Watering"]
    assert made[0]["data"]["note"] == 'From your note "Tomato pruning".'
    again = client.post(f"/whiteboard/boards/{bid}/nodes/{nid}/expand").json()
    assert [s["text"] for s in again["suggestions"]] == ["Drip lines"]


def test_the_menu_the_palette_and_the_guide_name_it():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    js = root / "frontend" / "js"
    mapjs = (js / "whiteboard-map.js").read_text(encoding="utf-8")
    body = mapjs[mapjs.index("async function wbMapExpandFromNote(node)") :]
    body = body[: body.index("\n}\n")]
    assert "/expand`, { method: \"POST\" }" in body and "wbMapBranchPicker(" in body
    assert "wbMapAddChosenBranches(node, boardId, chosen)" in body
    assert "function wbMapIsNoteTopic(node)" in mapjs
    commands = (js / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'id: "expand-from-note"' in commands and "notetopic: () => wbMapIsNoteTopic(" in commands
    board = (js / "whiteboard.js").read_text(encoding="utf-8")
    assert 'sub("Expand from my notes…"' in board and "if (wbMapIsNoteTopic(mapNode))" in board
    guide = (root / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Expand from my notes…" in guide
