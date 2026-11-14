"""L-documents-60: `direction` inside a subgraph is that group's own `dir`; at the top it stays a kept line."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_diagram_model import _run

ROOT = Path(__file__).resolve().parents[1]
SRC = "flowchart TD\n  subgraph S [Row]\n    direction LR\n    A --> B\n    subgraph T\n      direction TB\n      C\n    end\n  end\n  direction RL\n  B --> D\n"


def _go(src: str):
    body = f"""const m = diagramModel.parse({json.dumps(src)});
const once = diagramModel.print(m);
console.log(JSON.stringify({{ groups: m.subgraphs, kept: m.kept.map((k) => k.line), once, stable: diagramModel.print(diagramModel.parse(once)) === once }}));"""
    return _run(body)


def test_a_subgraph_direction_is_the_groups_dir_and_the_top_one_stays_kept():
    got = _go(SRC)
    assert {g["id"]: g.get("dir") for g in got["groups"]} == {"S": "LR", "T": "TD"}
    assert got["kept"] == ["direction RL"] and got["stable"]
    lines = got["once"].splitlines()
    assert lines[lines.index('  subgraph S ["Row"]') + 1] == "    direction LR"


def test_clearing_the_dir_drops_the_line_and_setting_it_writes_it():
    body = """const m = diagramModel.parse('flowchart TD\\n  subgraph S\\n    A\\n  end\\n');
m.subgraphs[0].dir = "BT";
const set = diagramModel.print(m);
delete m.subgraphs[0].dir;
console.log(JSON.stringify({ set, cleared: diagramModel.print(m) }));"""
    got = _run(body)
    assert "    direction BT" in got["set"] and "direction" not in got["cleared"]


def test_the_group_menu_offers_a_direction():
    js = (ROOT / "frontend/js/diagram-builder.js").read_text(encoding="utf-8")
    assert "Same as the diagram" in js and "g.dir" in js
