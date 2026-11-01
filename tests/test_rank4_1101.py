"""Audit 1031 ranked rows 7 and 13 (BD14, HR7, HR8): bounds and verdicts that were accepted or said in silence."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import tools
from tessellate.mcp_server import handle_request


def _call_search(arguments: dict) -> dict:
    reply = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_notes", "arguments": arguments}}
    )
    return json.loads(reply["result"]["content"][0]["text"])


def test_hr7_mcp_search_clamps_its_limit_and_reads_a_long_query(app_state):
    """HR7: `limit` 1,000,000,000 and a 100,000-character query were accepted."""
    from tessellate.core import deps
    from tessellate.entry import manager

    session = deps.get_db().session()
    try:
        for i in range(tools.MAX_LIST_LIMIT + 5):
            manager.create_entry(session, f"sourdough starter note {i}", category_name="Cooking")
    finally:
        session.close()
    huge = _call_search({"query": "sourdough " * 10_000, "limit": 1_000_000_000})
    assert 0 < len(huge["notes"]) <= tools.MAX_LIST_LIMIT
    assert len(huge["label"]) < 200


GOOD_SKETCHES = [
    "M0 0 L1 1",
    "[[1,2],[3,4]]",
    '{"d": "M0 0 L10 10 h-1.5e-7 z", "color": "#ff8800", "width": 2, "opacity": 0.5}',
    '{"type": "link-curved", "sourceId": 1, "targetId": 2, "color": "rgba(0,0,0,0.5)"}',
    '{"type": "rect", "d": "M0 0 h50 v50 h-50 z", "fill": "var(--accent)", "label": "x"}',
]
BAD_SKETCHES = [
    '{"d": "M0 0 <script>alert(1)</script>"}',
    '{"d": 5}',
    '{"color": "red; background:url(http://x)"}',
    '{"color": "' + "a" * 200 + '"}',
    '{"width": 1e9}',
    '{"width": -1}',
    '{"width": "wide"}',
    '{"opacity": 7}',
    '{"fill": "url(#x)"}',
    "[" * 150_000 + "]" * 150_000,
]


@pytest.mark.parametrize("data", GOOD_SKETCHES)
def test_bd14_a_sketch_a_page_can_draw_is_stored(client, data):
    r = client.post("/whiteboard/sketches", json={"data": data})
    assert r.status_code == 200, r.text
    assert r.json()["data"].startswith(data[:1])


@pytest.mark.parametrize("data", BAD_SKETCHES)
def test_bd14_a_sketch_path_colour_and_width_are_bounded_on_every_write(client, data):
    refused = client.post("/whiteboard/sketches", json={"data": data})
    assert refused.status_code == 422
    made = client.post("/whiteboard/sketches", json={"data": "M0 0 L1 1"}).json()
    edited = client.put(f"/whiteboard/sketches/{made['id']}", json={"data": data})
    assert edited.status_code == 422
    many = client.put("/whiteboard/items/save-many", json={"sketches": [{"id": made["id"], "data": data}]})
    assert many.status_code == 422
    board = client.post("/whiteboard/boards", json={"name": "B"}).json()
    paste = client.post(f"/whiteboard/boards/{board['id']}/paste", json={"items": [{"key": "a", "sketch": {"data": data}}]})
    assert paste.status_code == 422


def test_bd14_the_refusal_names_the_field_in_words(client):
    r = client.post("/whiteboard/sketches", json={"data": '{"width": 1e9}'})
    assert r.status_code == 422
    assert r.json()["fields"][0]["message"] == "The drawing's width is not something the board can draw."


def test_bd14_a_stored_row_the_rule_would_refuse_still_reads_back(client, app_state):
    """A row from before the rule is read, never refused: only a write is checked."""
    from tessellate.core import deps
    from tessellate.core.database import WhiteboardSketch

    session = deps.get_db().session()
    try:
        row = WhiteboardSketch(data='{"color": "' + "z" * 90 + '"}', x=0, y=0, z=0)
        session.add(row)
        session.commit()
        sketch_id = row.id
    finally:
        session.close()
    listed = client.get("/whiteboard/")
    assert listed.status_code == 200
    assert any(item["id"] == sketch_id for item in listed.json()["sketches"])


def test_hr8_a_bench_that_everything_failed_recommends_nothing(app_state):
    """HR8: "Recommended, Filing 0%, Answers 0%, Tools 0%"."""
    from tessellate.ai import bench
    from tessellate.core import deps
    from tests.test_bench_spec import Models, ScriptedModel, _seed

    session = deps.get_db().session()
    try:
        _seed(session)
        hopeless = ScriptedModel(wrong_category_for=" ", wrong_citation=True, no_tools=True)
        report = bench.run(session, Models({"m": hopeless}), ["m"], size=4)
    finally:
        session.close()
    row = report["models"][0]
    assert (row["filing"], row["citation"], row["tools"]) == (0.0, 0.0, 0.0)
    assert report["recommended"] is None
