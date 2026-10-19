"""The UML, entity relationship, wireframe and C4 sets and their three templates
(WHITEBOARD_PLAN, INBOX 1300 C04). Drawn here, nothing from draw.io."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "frontend" / "board-library"
SETS = {"uml": 23, "erd": 14, "wireframe": 19, "c4": 8}
TEMPLATES = {"uml-class", "erd", "wireframe"}


def _load(name):
    return json.loads((LIB / f"{name}.json").read_text(encoding="utf-8"))


def test_the_index_lists_the_three_sets_with_their_counts():
    index = {s["key"]: s for s in _load("index")["sets"]}
    for key, count in SETS.items():
        assert index[key]["count"] == count == len(_load(key)["items"])
    assert index["templates"]["count"] == len(_load("templates")["items"]) >= 20


@pytest.mark.parametrize("name", sorted(SETS))
def test_every_element_has_a_name_tags_and_a_box_its_drawing_stays_in(name):
    keys = set()
    for entry in _load(name)["items"]:
        assert entry["key"] not in keys
        keys.add(entry["key"])
        assert entry["name"][0].isupper() and entry["tags"]
        text = json.dumps(entry, ensure_ascii=False)
        assert chr(0x2014) not in text and "!" not in text
        box = entry["payload"]["box"]
        for item in entry["payload"]["items"]:
            if item["kind"] != "sketch":
                continue
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", re.sub(r"[AMLZ]", " ", item["data"]["d"]))]
            # Arc flags and radii are in the list too; the box bounds the coordinates, so check the largest.
            assert max(nums) <= max(box["w"], box["h"]) + 1, (entry["key"], item["key"])


def test_the_templates_link_only_to_whole_outlines():
    """A link anchors where a ray from the centre meets the path, so a linked
    sketch with a divider inside it ended its line inside the box (measured:
    52 px)."""
    by_key = {t["key"]: t for t in _load("templates")["items"]}
    assert TEMPLATES <= set(by_key)
    for key in TEMPLATES:
        payload = by_key[key]["payload"]
        items = {i["key"]: i for i in payload["items"]}
        assert by_key[key]["template"] == "board" and by_key[key]["purpose"] in {"plan", "solve"}
        assert len(by_key[key]["hint"]) <= 60 and by_key[key]["hint"][0].isupper()
        for link in payload["links"]:
            for end in (link["from"], link["to"]):
                assert items[end]["data"]["d"].count("M ") == 1, (key, end)


def test_the_erd_template_uses_the_crows_foot_ends_the_board_draws():
    ends = set()
    for link in next(t for t in _load("templates")["items"] if t["key"] == "erd")["payload"]["links"]:
        ends |= {link["data"].get("startCap"), link["data"].get("endCap")}
    assert {"er-one", "er-zero-many", "er-one-many"} <= ends


def test_a_class_box_places_on_a_board(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "Classes", "type": "board"}).json()
    placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "uml/class", "x": 0, "y": 0})
    assert placed.status_code == 201
    assert len(placed.json()["sketches"]) >= 3
    made = ai_client.post("/board-library/new-board", json={"builtin": "templates/erd", "name": "Tables"})
    assert made.status_code in (200, 201)


def test_the_new_wireframe_and_sequence_templates_exist_and_stand_on_their_own():
    by_key = {t["key"]: t for t in _load("templates")["items"]}
    assert {"wireframe-login", "wireframe-dashboard", "wireframe-mobile", "sequence"} <= set(by_key)
    for key in ("wireframe-login", "wireframe-dashboard", "wireframe-mobile", "sequence"):
        assert len(by_key[key]["payload"]["items"]) >= 10 and len(by_key[key]["hint"]) <= 60


def test_the_new_elements_are_findable_by_a_keyword():
    want = {"wireframe": {"phone", "toggle", "modal", "table", "icon-placeholder"},
            "uml": {"lifeline", "activation", "state", "component", "initial-state", "final-state"},
            "erd": {"associative-entity", "many-to-one"}}
    for name, keys in want.items():
        have = {e["key"]: e for e in _load(name)["items"]}
        assert keys <= set(have)
        assert all(len(have[k]["tags"]) >= 3 for k in keys)


def test_swimlanes_are_in_the_flowchart_set_with_a_search_keyword():
    index = {s["key"]: s for s in _load("index")["sets"]}
    items = {e["key"]: e for e in _load("flowchart")["items"]}
    assert index["flowchart"]["count"] == len(items)
    assert {"swimlane-h2", "swimlane-h3", "swimlane-v3"} <= set(items)
    assert all("swimlane" in items[k]["tags"] for k in ("swimlane-h2", "swimlane-h3", "swimlane-v3"))


def test_the_c4_set_places_through_the_route(ai_client):
    """WHITEBOARD_PLAN gap row 10 (INBOX 1308): person, systems, containers, boundary."""
    board = ai_client.post("/whiteboard/boards", json={"name": "Context"}).json()
    placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "c4/person", "x": 0, "y": 0})
    assert placed.status_code == 201, placed.text
    assert len({s["group_id"] for s in placed.json()["sketches"]}) == 1, "head and body move as one"
    keys = {e["key"] for e in _load("c4")["items"]}
    assert {"person", "software-system", "container", "container-database", "boundary", "external-system"} <= keys
