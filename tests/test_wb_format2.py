"""Board format, round two (WHITEBOARD_PLAN, wbformat2): picture border, grid size and colour, board options,
paper size, PNG and HTML export, rulers and units.

The server half runs through the API; the pure writers and readers run in node against the source."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERCHANGE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")


def app_js_text() -> str:
    """The whiteboard's scripts (they load apart from the app's boot scripts, so `tests/_app_js.py` does not hold them)."""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "js").glob("whiteboard*.js")))


def _node(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout.strip()


def _board(client, kind="board"):
    return client.post("/whiteboard/boards", json={"name": "Format two", "type": kind}).json()


def _pure_interchange() -> str:
    return INTERCHANGE[: INTERCHANGE.index("//: The rows inside an SVG")]


# --- 1. Picture border ------------------------------------------------------------------------------------


def test_a_picture_border_round_trips_and_its_width_is_bounded(ai_client):
    data = {"url": "/media/a.png", "border_color": "#112233", "border_width": 3}
    made = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": data, "x": 0, "y": 0, "width": 80, "height": 60})
    assert made.status_code == 201, made.text
    stored = ai_client.get("/whiteboard/").json()["objects"][0]["data"]
    assert (stored["border_color"], stored["border_width"]) == ("#112233", 3)
    too_wide = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {**data, "border_width": 99}, "x": 0, "y": 0, "width": 80, "height": 60})
    assert too_wide.status_code == 422


def test_a_picture_border_has_format_fields_a_render_and_an_export():
    js = app_js_text()
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-fmt="imageborder"' in html and 'id="wb-fmt-ibcolor"' in html and 'id="wb-fmt-ibwidth"' in html
    assert '"imageborder"' in js and "border_width" in js
    # Drawn on the board as an outline, and in the export as a stroked path over the picture.
    assert "obj.data.border_width" in js and "outlineOffset" in js


def test_a_picture_border_survives_a_drawio_round_trip():
    state = {"nodes": [], "sketches": [], "objects": [
        {"id": 1, "kind": "image", "x": 10, "y": 20, "width": 120, "height": 80, "z": 1, "data": {"url": "/media/a.png", "border_color": "#aa0011", "border_width": 4}}]}
    out = json.loads(_node(_pure_interchange() + f"\nconsole.log(JSON.stringify(wbBoardToDrawio({json.dumps(state)}, {{ box: () => null }})));"))
    xml = out["xml"]
    assert "shape=image" in xml and "imageBorder=#aa0011" in xml and "strokeWidth=4" in xml and "image=/media/a.png" in xml
    assert out["skipped"].get("pictures") is None
    style = "shape=image;image=/media/a.png;imageBorder=#aa0011;strokeWidth=4;"
    cells = [{"id": "0"}, {"id": "1", "parent": "0"}, {"id": "2", "parent": "1", "vertex": True, "style": style, "value": "", "geo": {"x": 10, "y": 20, "width": 120, "height": 80}}]
    plan = json.loads(_node(_pure_interchange() + f"\nconsole.log(JSON.stringify(wbDrawioPlan({json.dumps(cells)}).items));"))
    assert plan[0]["kind"] == "image" and plan[0]["url"] == "/media/a.png"
    assert plan[0]["look"] == {"border_color": "#aa0011", "border_width": 4}
