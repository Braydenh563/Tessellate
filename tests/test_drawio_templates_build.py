"""draw.io's templates as a library set (WHITEBOARD_PLAN section 8, row 980): the converter in
`scripts/build_drawio_templates.py`, five source files kept as fixtures, and the shipped set.

The converter runs the app's own cell planner in node, so a template here is what importing the
same `.drawio` file would put on a board.
"""

import html
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "drawio_templates"
SET = ROOT / "frontend" / "board-library" / "drawio-templates.json"
NOTE = "Template by JGraph, CC BY 4.0"

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("build_drawio_templates", ROOT / "scripts" / "build_drawio_templates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tool, tmp_path_factory):
    """The five fixtures laid out as the upstream folders, converted."""
    src = tmp_path_factory.mktemp("templates")
    for n, path in enumerate(sorted(FIXTURES.glob("*.xml"))):
        (src / f"f{n}").mkdir()
        shutil.copy(path, src / f"f{n}" / path.name)
    return tool.build(src, 5)


def _plain(text: str) -> str:
    return "".join(html.unescape(re.sub(r"<[^>]+>", " ", text or "")).split())


def test_five_templates_round_trip_shapes_links_and_labels(tool, built):
    assert len(built["items"]) == 5
    by_name = {i["name"].lower().replace(" ", "_"): i for i in built["items"]}
    for path in sorted(FIXTURES.glob("*.xml")):
        cells = tool.cells_of(tool.model_of(path))
        payload = by_name[path.stem]["payload"]
        shapes = [c for c in cells if c["vertex"]]
        ends = {c["id"] for c in shapes}
        links = [c for c in cells if c["edge"] and c["source"] in ends and c["target"] in ends]
        assert len(payload["items"]) == len(shapes), path.stem
        assert len(payload["links"]) == len(links), path.stem
        said = sorted(t for t in (_plain(c["value"]) for c in shapes) if t)
        have = sorted(t for t in (_plain((i["data"].get("label") or i["data"].get("content") or i["data"].get("text") or "")) for i in payload["items"]) if t)
        assert have == said, path.stem


def test_every_entry_carries_the_credit_and_a_library_shape(built):
    for entry in built["items"]:
        assert entry["note"] == NOTE
        assert entry["kind"] == "element" and entry["template"] == "board" and entry["tags"]
        assert entry["payload"]["box"]["w"] > 0 and entry["payload"]["items"]
    assert built["source"]["licence"] == "CC-BY-4.0" and built["source"]["note"] == NOTE


def test_the_shipped_set_has_forty_and_the_index_counts_them():
    data = json.loads(SET.read_text(encoding="utf-8"))
    assert data["key"] == "drawio-templates" and len(data["items"]) == 40
    keys = [e["key"] for e in data["items"]]
    assert len(set(keys)) == 40
    assert all(e["note"] == NOTE for e in data["items"])
    text = SET.read_text(encoding="utf-8")
    assert chr(0x2014) not in text
    index = {s["key"]: s for s in json.loads((ROOT / "frontend" / "board-library" / "index.json").read_text(encoding="utf-8"))["sets"]}
    assert index["drawio-templates"]["count"] == 40


def test_the_shipped_templates_place_on_a_board(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "From draw.io"}).json()
    data = json.loads(SET.read_text(encoding="utf-8"))
    first = data["items"][0]
    out = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": f"drawio-templates/{first['key']}", "x": 0, "y": 0})
    assert out.status_code == 201 and out.json()["sketches"], out.text[:200]
