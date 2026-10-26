"""The board's object library (WHITEBOARD_PLAN decision 25; INBOX 557c, 558).

The owner: "an object or elements library would be really good like with what
draw.io has", and "the ability to save custom elements and stuff as well".
What the API promises, tested here: the six kinds of "Yours" save and list;
a payload is held to its limits and to this notebook's own pictures; placing
makes independent rows in one transaction and one event, links and groups
remapped, paths moved and scaled; built-ins (static files) place the same
way; favourites and recent cover both; a library exports and imports with new
ids; media cleanup counts what the library holds. The browser half is
`scratchpad/ui-sweeps/wb1005-library.js`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.api.routes_board_library import transform_path


def _board(client, name="Library board", kind="board"):
    return client.post("/whiteboard/boards", json={"name": name, "type": kind}).json()


def _rect(x, y, w=100, h=60):
    return f"M {x} {y} L {x + w} {y} L {x + w} {y + h} L {x} {y + h} Z"


def _element(n_links=1):
    items = [
        {"key": "a", "kind": "sketch", "data": {"d": _rect(0, 0), "shape": "rect", "color": "#123456", "width": 2}, "z": 5, "group": "g"},
        {"key": "b", "kind": "sketch", "data": {"d": _rect(200, 0), "shape": "rect", "color": "#123456", "width": 2}, "z": 5, "group": "g"},
        {"key": "t", "kind": "object", "type": "text", "data": {"content": "Hello"}, "x": 0, "y": 100, "w": 120, "h": 40, "z": 1},
    ]
    links = [{"from": "a", "to": "b", "data": {"type": "link-straight", "color": "#000000"}}][:n_links]
    return {"box": {"w": 300, "h": 140}, "items": items, "links": links}


def _save(client, kind="element", payload=None, name="Three things", tags=("demo",)):
    out = client.post("/board-library", json={"kind": kind, "name": name, "tags": list(tags), "payload": payload or _element()})
    assert out.status_code == 201, out.text
    return out.json()


def test_transform_path_moves_and_scales_every_command() -> None:
    assert transform_path("M 0 0 L 10 20 Z", 2, 3, 5, 7) == "M 5 7 L 25 67 Z"
    assert transform_path("M0 0C1 1 2 2 3 3", 1, 1, 10, 10) == "M 10 10 C 11 11 12 12 13 13"
    assert transform_path("M 0 0 h 10 v 5 a 5 5 0 0 1 10 0", 2, 2, 1, 1) == "M 1 1 h 20 v 10 a 10 10 0 0 1 20 0"
    assert transform_path("M 0 0 A 50 25 0 1 1 100 0", 0.5, 2, 0, 0) == "M 0 0 A 25 50 0 1 1 50 0"


def test_save_list_and_place_a_selection_twice(ai_client):
    board = _board(ai_client)
    item = _save(ai_client)
    listed = ai_client.get("/board-library").json()
    assert any(i["id"] == item["id"] for i in listed["items"])
    assert {s["key"] for s in listed["sets"]} >= {"general", "flowchart", "arrows", "frames", "icons"}
    for x in (0, 1000):
        out = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": x, "y": 0})
        assert out.status_code == 201, out.text
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    links = [s for s in state["sketches"] if json.loads(s["data"]).get("type", "").startswith("link-")]
    shapes = [s for s in state["sketches"] if s not in links]
    assert len(shapes) == 4 and len(state["objects"]) == 2 and len(links) == 2
    #: Each placement's link joins its own two shapes, not the first copy's.
    shape_ids = {s["id"] for s in shapes}
    pairs = {(json.loads(lk["data"])["sourceId"], json.loads(lk["data"])["targetId"]) for lk in links}
    assert len(pairs) == 2 and all(a in shape_ids and b in shape_ids for a, b in pairs)
    #: Groups are new per placement.
    groups = {s["group_id"] for s in shapes}
    assert len(groups) == 2 and None not in groups
    #: Independent copies that remember where they came from.
    ref = json.loads(shapes[0]["data"])["library_ref"]
    assert ref == {"id": item["id"], "version": 1}
    #: Centred on the point asked for: the 300-wide box at x=1000.
    xs = sorted(o["x"] for o in state["objects"])
    assert xs == [-150, 850]
    used = ai_client.get("/board-library").json()
    assert used["recent"][0] == f"item:{item['id']}"


def test_one_placement_is_one_board_event_and_each_item_replays(ai_client):
    """One board event names the placement and its rows; each row has its own
    `created` too, so a placed item replays like one drawn by hand (the
    board's time machine, WHITEBOARD_PLAN decision 33). It was one event in
    all, the rows' folded in with their values dropped."""
    board = _board(ai_client)
    item = _save(ai_client)
    def count(kind):
        return len(ai_client.get(f"/audit?entity_type={kind}&limit=500").json())

    before = {k: count(k) for k in ("board", "whiteboard_sketch", "whiteboard_object")}
    placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": 0, "y": 0}).json()
    after = {k: count(k) for k in before}
    assert after["board"] == before["board"] + 1
    assert after["whiteboard_sketch"] == before["whiteboard_sketch"] + len(placed["sketches"])
    assert after["whiteboard_object"] == before["whiteboard_object"] + len(placed["objects"])
    event = ai_client.get("/audit?entity_type=board&limit=1").json()[0]
    assert event["action"] == "placed"
    moment = ai_client.get("/whiteboard/history", params={"board_id": board["id"]}).json()["moments"][0]
    shown = ai_client.get(f"/whiteboard/history/{moment['id']}", params={"board_id": board["id"]}).json()
    assert {s["id"] for s in shown["sketches"]} == {s["id"] for s in placed["sketches"]}
    assert {o["id"] for o in shown["objects"]} == {o["id"] for o in placed["objects"]}


def test_a_builtin_places_and_takes_the_pen_colour(ai_client):
    board = _board(ai_client)
    out = ai_client.post(
        f"/whiteboard/boards/{board['id']}/place",
        json={"builtin": "flowchart/decision", "x": 0, "y": 0, "ink": "#aa3300", "w": 320, "h": 200},
    )
    assert out.status_code == 201, out.text
    data = json.loads(out.json()["sketches"][0]["data"])
    assert data["color"] == "#aa3300" and data["fill"] == "#aa3300"
    assert data["shape"] == "custom" and data["library_ref"] == {"builtin": "flowchart/decision"}
    #: Scaled to the size asked for: the 160x100 diamond is now 320 wide.
    assert data["d"].startswith("M 0 -100")
    icon = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "icons/acorn", "x": 0, "y": 0})
    assert icon.status_code == 201, icon.text
    assert json.loads(icon.json()["sketches"][0]["data"])["icon"] == "acorn"
    missing = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "flowchart/nope", "x": 0, "y": 0})
    assert missing.status_code == 404


def test_favourites_cover_builtins_and_yours(ai_client):
    item = _save(ai_client)
    ai_client.put(f"/board-library/{item['id']}", json={"favourite": True})
    ai_client.post("/board-library/marks", json={"key": "general/star", "favourite": True})
    listed = ai_client.get("/board-library").json()
    assert listed["marks"]["general/star"]["favourite"] is True
    assert [i for i in listed["items"] if i["id"] == item["id"]][0]["favourite"] is True
    reply_1 = ai_client.post("/board-library/marks", json={"key": "general/nope", "favourite": True})
    assert reply_1.status_code == 404


def test_rename_payload_bumps_version_delete_restore_duplicate(ai_client):
    item = _save(ai_client)
    renamed = ai_client.put(f"/board-library/{item['id']}", json={"name": "Renamed", "tags": ["A", "a", "b"]}).json()
    assert renamed["name"] == "Renamed" and renamed["tags"] == ["a", "b"] and renamed["version"] == 1
    bumped = ai_client.put(f"/board-library/{item['id']}", json={"payload": _element(n_links=0)}).json()
    assert bumped["version"] == 2
    ai_client.delete(f"/board-library/{item['id']}")
    assert not any(i["id"] == item["id"] for i in ai_client.get("/board-library").json()["items"])
    assert any(i["id"] == item["id"] for i in ai_client.get("/board-library?deleted=true").json()["items"])
    ai_client.post(f"/board-library/{item['id']}/restore")
    copy = ai_client.post(f"/board-library/{item['id']}/duplicate").json()
    assert copy["id"] != item["id"] and copy["name"] == "Renamed (copy)"


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("style", {"target": "shape", "style": {"color": "#112233", "fill": "#445566", "width": 3, "evil": "x"}}),
        ("palette", {"colours": ["#112233", "#AABBCC", "red", "#112233"]}),
        ("preset", {"box": {"w": 180, "h": 140}, "items": [{"key": "s", "kind": "object", "type": "text", "data": {"content": "Idea", "bg": "#fff4a3"}, "x": 0, "y": 0, "w": 180, "h": 140}]}),
        ("branch", {"nodes": [{"text": "Root", "children": [{"text": "A", "children": [{"text": "A1"}]}, {"text": "B"}]}]}),
        ("template", {"board": {"type": "board", "background": {"color": "#101820"}}, "element": None or {"box": {"w": 10, "h": 10}, "items": [{"key": "f", "kind": "object", "type": "frame", "data": {"content": "To do"}, "x": 0, "y": 0, "w": 300, "h": 200}]}}),
        ("shape", {"box": {"w": 1, "h": 1}, "items": [{"key": "s", "kind": "sketch", "data": {"d": "M 0 0 L 1 0 L 0.5 1 Z", "shape": "custom", "color": "ink"}}]}),
    ],
)
def test_every_kind_of_yours_saves(ai_client, kind, payload):
    saved = _save(ai_client, kind=kind, payload=payload, name=f"A {kind}")
    if kind == "style":
        assert "evil" not in saved["payload"]["style"]
    if kind == "palette":
        assert saved["payload"]["colours"] == ["#112233", "#aabbcc"]


def test_a_branch_places_under_a_topic(ai_client):
    board = _board(ai_client, name="Branch map", kind="map")
    root = ai_client.post(f"/whiteboard/boards/{board['id']}/nodes", json={"kind": "topic", "text": "Centre"}).json()
    item = _save(ai_client, kind="branch", payload={"nodes": [{"text": "Risks", "children": [{"text": "Cost"}, {"text": "Time"}]}]})
    out = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": 0, "y": 0, "parent_id": root["id"]})
    assert out.status_code == 201, out.text
    made = out.json()["objects"]
    risks = next(o for o in made if o["data"]["content"] == "Risks")
    assert risks["parent_id"] == root["id"]
    assert sorted(o["data"]["content"] for o in made if o["parent_id"] == risks["id"]) == ["Cost", "Time"]


def test_builtin_templates_place_on_a_board_and_under_a_topic(ai_client):
    """INBOX 596: preset board and map templates in the Library. A board
    template is an element (frames, stickies, shapes and their links); a map
    template is a branch, placed under the topic it is dropped on."""
    sets = {s["key"]: s for s in ai_client.get("/board-library").json()["sets"]}
    assert sets["templates"]["count"] >= 5 and sets["maps"]["count"] >= 7
    board = _board(ai_client)
    flow = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "templates/flow", "x": 0, "y": 0, "ink": "#223344"})
    assert flow.status_code == 201, flow.text
    shapes = [json.loads(s["data"]) for s in flow.json()["sketches"]]
    labels = {d.get("label") for d in shapes}
    assert {"Start", "Did it work?", "End"} <= labels
    links = [d for d in shapes if d.get("type", "").startswith("link-")]
    assert len(links) == 5 and all(d.get("sourceId") and d.get("targetId") for d in links)
    kanban = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "templates/kanban", "x": 0, "y": 0}).json()
    assert sum(o["kind"] == "frame" for o in kanban["objects"]) == 3 and sum(o["kind"] == "text" for o in kanban["objects"]) >= 4
    mind = _board(ai_client, name="Template map", kind="map")
    root = ai_client.post(f"/whiteboard/boards/{mind['id']}/nodes", json={"kind": "topic", "text": "Centre"}).json()
    out = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"builtin": "maps/brainstorm", "x": 0, "y": 0, "parent_id": root["id"]})
    assert out.status_code == 201, out.text
    made = out.json()["objects"]
    assert sorted(o["data"]["content"] for o in made if o["parent_id"] == root["id"]) == ["Ideas", "Next steps", "Questions", "Themes"]


def test_no_two_topics_of_a_placed_branch_share_a_spot(ai_client):
    """INBOX 664: the Decision template put "Option B" and "Cost" on the same
    spot (a row was the parent's row plus the child's index), which a map
    with no layout to tidy it kept, one box on top of another."""
    mind = _board(ai_client, name="Overlap map", kind="map")
    root = ai_client.post(f"/whiteboard/boards/{mind['id']}/nodes", json={"kind": "topic", "text": "Centre"}).json()
    for key in ("maps/decision", "maps/project", "maps/brainstorm"):
        out = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"builtin": key, "x": 100, "y": 50, "parent_id": root["id"]})
        assert out.status_code == 201, out.text
        spots = [(o["x"], o["y"]) for o in out.json()["objects"]]
        assert len(spots) == len(set(spots)), (key, spots)
        # A topic with children sits on its first child's row, one column left.
        made = out.json()["objects"]
        for topic in made:
            kids = [o for o in made if o["parent_id"] == topic["id"]]
            if kids:
                assert kids[0]["y"] == topic["y"] and kids[0]["x"] == topic["x"] + 220


def _objects(client, board_id):
    return client.get(f"/whiteboard/?board_id={board_id}").json()["objects"]


def test_a_template_on_a_map_with_no_centre_gets_one(ai_client):
    """INBOX 670: a map template dropped on a map with no central topic made
    one trunk per top-level topic. Several top-level topics now go under a new
    central topic named after the template; one becomes the centre itself."""
    mind = _board(ai_client, name="Rootless map", kind="map")
    out = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"builtin": "maps/brainstorm", "x": 0, "y": 0})
    assert out.status_code == 201, out.text
    made = out.json()["objects"]
    roots = [o for o in made if o["parent_id"] is None]
    assert [o["data"]["content"] for o in roots] == ["Brainstorm"]
    kids = [o for o in made if o["parent_id"] == roots[0]["id"]]
    assert sorted(o["data"]["content"] for o in kids) == ["Ideas", "Next steps", "Questions", "Themes"]
    # The centre sits on its first branch's row, one column left, and no two
    # topics share a spot.
    assert kids[0]["y"] == roots[0]["y"] and kids[0]["x"] == roots[0]["x"] + 220
    spots = [(o["x"], o["y"]) for o in made]
    assert len(spots) == len(set(spots))


def test_a_template_with_one_top_level_topic_makes_it_the_centre(ai_client):
    mind = _board(ai_client, name="Rootless single", kind="map")
    item = _save(ai_client, kind="branch", name="Risks", payload={"nodes": [{"text": "Risks", "children": [{"text": "Cost"}, {"text": "Time"}]}]})
    out = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"item_id": item["id"], "x": 0, "y": 0})
    assert out.status_code == 201, out.text
    made = out.json()["objects"]
    assert [o["data"]["content"] for o in made if o["parent_id"] is None] == ["Risks"]
    assert len(made) == 3


def test_a_template_on_a_map_that_has_a_centre_adds_no_second_one(ai_client):
    mind = _board(ai_client, name="Centred map", kind="map")
    root = ai_client.post(f"/whiteboard/boards/{mind['id']}/nodes", json={"kind": "topic", "text": "Centre"}).json()
    under = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"builtin": "maps/brainstorm", "x": 0, "y": 0, "parent_id": root["id"]}).json()["objects"]
    assert not any(o["parent_id"] is None for o in under)
    assert not any(o["data"]["content"] == "Brainstorm" for o in under)
    # No parent given on a map that already has a root: nothing is wrapped.
    bare = ai_client.post(f"/whiteboard/boards/{mind['id']}/place", json={"builtin": "maps/decision", "x": 0, "y": 0}).json()["objects"]
    assert not any(o["data"]["content"] == "Decision" for o in bare)


def test_a_template_on_a_plain_board_is_not_wrapped(ai_client):
    board = _board(ai_client, name="Plain board")
    made = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "maps/brainstorm", "x": 0, "y": 0}).json()["objects"]
    assert not any(o["data"]["content"] == "Brainstorm" for o in made)


def test_a_new_map_from_a_map_template_has_one_centre(ai_client):
    out = ai_client.post("/board-library/new-board", json={"builtin": "maps/project", "name": "Launch"})
    assert out.status_code == 201, out.text
    topics = _objects(ai_client, out.json()["id"])
    roots = [o for o in topics if o["parent_id"] is None]
    # The centre is the map's own name (INBOX 715), as a blank map's is.
    assert [o["data"]["content"] for o in roots] == ["Launch"]
    assert sum(o["parent_id"] == roots[0]["id"] for o in topics) == 5


def test_a_template_starts_a_board_with_its_look(ai_client):
    item = _save(ai_client, kind="template", payload={
        "board": {"type": "board", "background": {"color": "#101820"}},
        "element": {"box": {"w": 300, "h": 200}, "items": [{"key": "f", "kind": "object", "type": "frame", "data": {"content": "To do"}, "x": 0, "y": 0, "w": 300, "h": 200}]},
    })
    out = ai_client.post("/board-library/new-board", json={"item_id": item["id"], "name": "From a template"})
    assert out.status_code == 201, out.text
    state = ai_client.get(f"/whiteboard/?board_id={out.json()['id']}").json()
    assert state["background"]["color"] == "#101820"
    assert [o["kind"] for o in state["objects"]] == ["frame"]
    kanban = ai_client.post("/board-library/new-board", json={"builtin": "templates/kanban", "name": "Sprint"}).json()
    assert sum(o["kind"] == "frame" for o in ai_client.get(f"/whiteboard/?board_id={kanban['id']}").json()["objects"]) == 3


def test_limits_and_pictures(ai_client):
    big = {"box": {"w": 1, "h": 1}, "items": [{"key": f"k{i}", "kind": "object", "type": "text", "data": {"content": "x"}, "x": 0, "y": 0, "w": 20, "h": 20} for i in range(501)]}
    reply_2 = ai_client.post("/board-library", json={"kind": "element", "name": "Too many", "payload": big})
    assert reply_2.status_code == 422
    outside = {"box": {"w": 1, "h": 1}, "items": [{"key": "p", "kind": "object", "type": "image", "data": {"url": "https://example.com/x.png"}, "x": 0, "y": 0, "w": 20, "h": 20}]}
    reply_3 = ai_client.post("/board-library", json={"kind": "element", "name": "Outside", "payload": outside})
    assert reply_3.status_code == 422
    huge = {"box": {"w": 1, "h": 1}, "items": [{"key": "s", "kind": "sketch", "data": {"d": "M 0 0 " + "L 1 1 " * 120000}}]}
    reply_4 = ai_client.post("/board-library", json={"kind": "element", "name": "Huge", "payload": huge})
    assert reply_4.status_code == 422
    reply_5 = ai_client.post("/board-library", json={"kind": "nonsense", "name": "X", "payload": {}})
    assert reply_5.status_code == 422


def test_export_then_import_gives_new_ids_and_drops_strangers(ai_client):
    picture = ai_client.post("/media/upload", files={"file": ("p.png", b"\x89PNG\r\n\x1a\n", "image/png")}).json()
    with_picture = {"box": {"w": 100, "h": 100}, "items": [{"key": "p", "kind": "object", "type": "image", "data": {"url": picture["url"]}, "x": 0, "y": 0, "w": 100, "h": 100}]}
    first = _save(ai_client, name="Exported one")
    _save(ai_client, payload=with_picture, name="With a picture")
    listed = ai_client.get("/board-library").json()
    exported = ai_client.get(f"/board-library/export?library_id={listed['yours_id']}")
    assert exported.status_code == 200
    body = exported.json()
    assert body["format"] == "memorymap-library" and len(body["items"]) >= 2
    body["items"].append({"kind": "element", "name": "Stranger", "payload": {"box": {"w": 1, "h": 1}, "items": [
        {"key": "p", "kind": "object", "type": "image", "data": {"url": "/media/not-here.png"}, "x": 0, "y": 0, "w": 20, "h": 20},
        {"key": "t", "kind": "object", "type": "text", "data": {"content": "kept"}, "x": 0, "y": 0, "w": 20, "h": 20},
    ]}})
    result = ai_client.post("/board-library/import", json=body).json()
    assert result["items"] == len(body["items"]) and result["dropped_media"] == 1
    imported = ai_client.get(f"/board-library?library_id={result['library']['id']}").json()["items"]
    assert first["id"] not in {i["id"] for i in imported}
    stranger = next(i for i in imported if i["name"] == "Stranger")
    assert [it["key"] for it in stranger["payload"]["items"]] == ["t"]
    reply_6 = ai_client.post("/board-library/import", json={"format": "other", "items": []})
    assert reply_6.status_code == 422


def test_media_in_the_library_is_not_an_orphan(ai_client):
    picture = ai_client.post("/media/upload", files={"file": ("q.png", b"\x89PNG\r\n\x1a\n", "image/png")}).json()
    _save(ai_client, payload={"box": {"w": 10, "h": 10}, "items": [
        {"key": "p", "kind": "object", "type": "image", "data": {"url": picture["url"]}, "x": 0, "y": 0, "w": 20, "h": 20}]})
    orphans = ai_client.get("/media/orphans").json()["orphans"]
    assert not any(o["url"] == picture["url"] for o in orphans)


def test_a_deleted_library_comes_back_with_its_items(ai_client):
    """INBOX 898: deleting a library moves its items to Yours; Undo puts the
    library back and the items in it. An import's undo takes the items too."""
    made = ai_client.post("/board-library/libraries", json={"name": "Flow"}).json()
    item = ai_client.post(
        "/board-library",
        json={"kind": "element", "name": "Boxes", "payload": _element(), "library_id": made["id"]},
    ).json()
    yours = ai_client.get("/board-library").json()["yours_id"]

    gone = ai_client.delete(f"/board-library/libraries/{made['id']}").json()
    assert gone["moved"] == 1 and gone["undo_token"]
    moved = ai_client.get(f"/board-library?library_id={yours}").json()["items"]
    assert item["id"] in {i["id"] for i in moved}

    back = ai_client.post("/board-library/libraries/restore", json={"token": gone["undo_token"]})
    assert back.status_code == 201 and back.json()["id"] == made["id"]
    inside = ai_client.get(f"/board-library?library_id={made['id']}").json()["items"]
    assert [i["id"] for i in inside] == [item["id"]]
    reply_7 = ai_client.post("/board-library/libraries/restore", json={"token": gone["undo_token"]})
    assert reply_7.status_code == 404


def test_deleting_an_import_with_its_items_is_undone_whole(ai_client):
    _save(ai_client, name="Seed")
    yours = ai_client.get("/board-library").json()["yours_id"]
    body = ai_client.get(f"/board-library/export?library_id={yours}").json()
    result = ai_client.post("/board-library/import", json=body).json()
    library_id = result["library"]["id"]
    assert ai_client.get(f"/board-library?library_id={library_id}").json()["items"]

    gone = ai_client.delete(f"/board-library/libraries/{library_id}?with_items=true").json()
    assert ai_client.get(f"/board-library?library_id={yours}").json()["items"] == ai_client.get(
        f"/board-library?library_id={yours}"
    ).json()["items"]
    assert len(ai_client.get(f"/board-library?library_id={yours}").json()["items"]) == 1

    ai_client.post("/board-library/libraries/restore", json={"token": gone["undo_token"]})
    assert len(ai_client.get(f"/board-library?library_id={library_id}").json()["items"]) == result["items"]
    assert len(ai_client.get(f"/board-library?library_id={yours}").json()["items"]) == 1


# A Library tile draws what placing it makes (INBOX 794).
ROOT = Path(__file__).resolve().parents[1]


def test_a_library_tile_draws_what_placing_it_makes():
    """INBOX 794: the board Library's shape tiles drew every ink as the page's
    text colour, a faint fill lifted to 18% and one hairline, so with a cyan pen
    a placed shape was cyan and its tile was grey. `placed` resolves the ink to
    the pen's, and keeps the payload's own fill opacity, width and dash (the
    board's own dash ratios). Run against the shipped shapes and the board's
    own `wbDashArray`."""
    import shutil
    import subprocess


    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    templates = (ROOT / "frontend" / "js" / "whiteboard-templates.js").read_text(encoding="utf-8")
    board = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")

    def fn(src: str, name: str) -> str:
        start = src.index(f"function {name}(")
        return src[start : src.index("\n}\n", start) + 3]

    shapes = json.loads((ROOT / "frontend" / "board-library" / "general.json").read_text(encoding="utf-8"))["items"][:6]
    dashed = {"box": {"w": 100, "h": 100}, "items": [{"key": "a", "kind": "sketch", "data": {"d": "M 0 0 L 90 0", "color": "ink", "width": 4, "dash": "dashed"}}]}
    dotted = json.loads(json.dumps(dashed).replace("dashed", "dotted"))
    payloads = [s["payload"] for s in shapes] + [dashed, dotted]
    script = (
        fn(templates, "wbThumbRound") + fn(templates, "wbBoardThumbSpec") + fn(board, "wbDashArray")
        + f"const P = {json.dumps(payloads)};"
        + "console.log(JSON.stringify({"
        + "placed: P.map((p) => wbBoardThumbSpec(p, { placed: true, ink: '#00bcd4' }).parts.filter((x) => x.tag === 'path').map((x) => x.a)),"
        + "plain: P.map((p) => wbBoardThumbSpec(p).parts.filter((x) => x.tag === 'path').map((x) => x.a)),"
        + "dash: [wbDashArray('dashed', 4), wbDashArray('dotted', 4)]"
        + "}));"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    for payload, placed, plain in zip(payloads, out["placed"], out["plain"]):
        sketches = [i for i in payload["items"] if i["kind"] == "sketch"]
        for item, tile, old in zip(sketches, placed, plain):
            data = item["data"]
            if data.get("color") == "ink":
                assert tile["stroke"] == "#00bcd4" and old["stroke"] == "currentColor"
            if data.get("fill") == "ink":
                assert tile["fill"] == "#00bcd4"
                assert tile["fill-opacity"] == str(data["fillOpacity"]), "the tile lifts no fill"
            if data.get("width"):
                assert tile["stroke-width"] == data["width"]
    dashes = [tile.get("stroke-dasharray") for tile in out["placed"][-2] + out["placed"][-1]]
    assert dashes == out["dash"], dashes


def _zs(state):
    sketches = {s["id"]: s["z"] for s in state["sketches"]}
    return sketches, {o["id"]: o["z"] for o in state["objects"]}


def test_a_placement_lands_on_top_of_what_is_already_there(ai_client):
    """wb5: a stencil carries z 5 (drawings) and 1 (cards, links); a board
    already holding higher ones had the placement land under or tied with
    them. Each band takes the next z, the stencil's own order kept."""
    board = _board(ai_client)
    old_sketch = ai_client.post("/whiteboard/sketches", json={"data": json.dumps({"d": _rect(0, 0), "shape": "rect"}), "x": 0, "y": 0, "z": 40, "board_id": board["id"]}).json()
    old_box = ai_client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "old"}, "board_id": board["id"], "x": 0, "y": 0, "z": 30, "width": 100, "height": 60}).json()
    old_frame = ai_client.post("/whiteboard/objects", json={"kind": "frame", "data": {"content": "f"}, "board_id": board["id"], "x": 0, "y": 0, "z": -3, "width": 100, "height": 60}).json()
    item = _save(ai_client)
    for _ in range(2):
        placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": 500, "y": 0})
        assert placed.status_code == 201
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    sketches, objects = _zs(state)
    new_sketch = [z for i, z in sketches.items() if i != old_sketch["id"]]
    new_box = [z for i, z in objects.items() if i not in (old_box["id"], old_frame["id"])]
    assert min(new_sketch) > sketches[old_sketch["id"]] and len(set(new_sketch)) == len(new_sketch)
    assert min(new_box) > objects[old_box["id"]] and len(set(new_box)) == len(new_box)
    #: The link (z 1 in the stencil) stays under its two shapes (z 5).
    first = [s for s in state["sketches"] if s["id"] != old_sketch["id"]][:3]
    link = next(s for s in first if json.loads(s["data"]).get("type", "").startswith("link-"))
    assert all(link["z"] < s["z"] for s in first if s is not link)


def test_a_placed_frame_goes_under_the_frames_already_there(ai_client):
    board = _board(ai_client)
    old = ai_client.post("/whiteboard/objects", json={"kind": "frame", "data": {"content": "f"}, "board_id": board["id"], "x": 0, "y": 0, "z": 4, "width": 100, "height": 60}).json()
    frame = {"box": {"w": 10, "h": 10}, "items": [{"key": "f", "kind": "object", "type": "frame", "data": {"content": "New"}, "x": 0, "y": 0, "w": 300, "h": 200, "z": 1}], "links": []}
    item = _save(ai_client, payload=frame)
    placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"item_id": item["id"], "x": 0, "y": 0})
    assert placed.status_code == 201
    _, objects = _zs(ai_client.get(f"/whiteboard/?board_id={board['id']}").json())
    assert min(objects.values()) < objects[old["id"]] == 4
