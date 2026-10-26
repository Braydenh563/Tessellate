"""The student and personal templates (WHITEBOARD_PLAN 1355): each one starts
a board, every key is unique, hints fit the picker, and the Venn, timeline
and brainstorm pictures carry their shapes and links."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parent.parent / "frontend" / "board-library"
NEW_BOARDS = ["lecture", "revision", "essay", "timeline", "venn", "brainstorm", "concept", "timetable",
              "habits", "smart", "project-plan", "reading", "exam", "day"]
NEW_MAPS = ["lecture-map", "revision-map", "exam-map", "research-map", "presentation-map", "group-map",
            "goals-map", "routine-map", "career-map", "reading-map", "habits-map", "moving-map"]


def _items(name):
    return json.loads((LIB / f"{name}.json").read_text())["items"]


def test_keys_are_unique_and_hints_fit():
    for name in ("templates", "maps"):
        items = _items(name)
        keys = [i["key"] for i in items]
        assert len(keys) == len(set(keys))
        assert all(len(i["hint"]) <= 64 and i["name"] for i in items)
    assert set(NEW_BOARDS) <= {i["key"] for i in _items("templates")}
    assert set(NEW_MAPS) <= {i["key"] for i in _items("maps")}


def test_item_keys_inside_a_template_are_unique_and_links_resolve():
    for item in _items("templates"):
        payload = item["payload"]
        keys = [p["key"] for p in payload.get("items", [])]
        assert len(keys) == len(set(keys)), item["key"]
        for link in payload.get("links", []):
            assert link["from"] in keys and link["to"] in keys, item["key"]


@pytest.mark.parametrize("key", NEW_BOARDS)
def test_a_new_board_template_starts_a_board(ai_client, key):
    made = ai_client.post("/board-library/new-board", json={"builtin": f"templates/{key}", "name": "T " + key})
    assert made.status_code == 201, made.text
    assert made.json()["type"] == "board"


@pytest.mark.parametrize("key", NEW_MAPS)
def test_a_new_map_template_starts_a_map(ai_client, key):
    made = ai_client.post("/board-library/new-board", json={"builtin": f"maps/{key}", "name": "M " + key})
    assert made.status_code == 201, made.text
    assert made.json()["type"] == "map"


def test_brainstorm_joins_the_idea_to_six_notes():
    brainstorm = next(i for i in _items("templates") if i["key"] == "brainstorm")
    assert len(brainstorm["payload"]["links"]) == 6


def test_callouts_set_is_listed_and_every_element_places(ai_client):
    index = json.loads((LIB / "index.json").read_text())
    row = next(s for s in index["sets"] if s["key"] == "callouts")
    items = _items("callouts")
    assert row["count"] == len(items) >= 14
    board = ai_client.post("/whiteboard/boards", json={"name": "Callouts", "type": "board"}).json()
    for item in items:
        placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": f"callouts/{item['key']}", "x": 0, "y": 0})
        assert placed.status_code == 201, (item["key"], placed.text)
