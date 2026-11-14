"""L-documents-58: an arrow's id and animation (`e1@-->`, `e1@{ animate: true }`) are the model's own; the menu entry is in the lazy style file."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_diagram_model import _run

ROOT = Path(__file__).resolve().parents[1]


def _go(src: str):
    body = f"""const m = diagramModel.parse({json.dumps(src)});
const once = diagramModel.print(m);
console.log(JSON.stringify({{ m, kept: m.kept.map((k) => k.line), once, stable: diagramModel.print(diagramModel.parse(once)) === once }}));"""
    return _run(body)


def test_an_edge_id_and_its_animate_line_are_lifted_into_the_edge():
    got = _go("flowchart LR\n  A e1@--> B\n  B e2@==>|go| C\n  e1@{ animate: true }\n  e2@{ animate: true, animation: slow }\n")
    e1, e2 = got["m"]["edges"]
    assert e1["id"] == "e1" and e1["animate"] == "on" and e2["id"] == "e2" and e2["animate"] == "slow" and e2["label"] == "go"
    assert got["kept"] == [] and [n["id"] for n in got["m"]["nodes"]] == ["A", "B", "C"]


def test_they_print_back_in_one_form_and_are_stable():
    got = _go("flowchart LR\n  A e1@--> B\n  e1@{ animation: fast }\n  B --> C\n")
    lines = [line.strip() for line in got["once"].splitlines()]
    assert "A e1@--> B" in lines and "e1@{ animate: true, animation: fast }" in lines and got["stable"]
    assert lines.index("e1@{ animate: true, animation: fast }") == lines.index("A e1@--> B") + 1


def test_an_edge_set_to_move_in_the_model_gets_a_free_id():
    body = """const m = diagramModel.parse('flowchart LR\\n  e1 --> B\\n');
m.edges[0].animate = 'on';
const once = diagramModel.print(m);
console.log(JSON.stringify({ once, back: diagramModel.parse(once).edges[0] }));"""
    got = _run(body)
    assert "e1 e2@--> B" in got["once"] and "e2@{ animate: true }" in got["once"]
    assert got["back"]["id"] == "e2" and got["back"]["animate"] == "on"


def test_other_keys_of_the_line_are_kept_and_a_plain_edge_prints_unchanged():
    got = _go("flowchart LR\n  A e1@--> B\n  e1@{ animate: true, curve: basis }\n  B --> C\n")
    assert got["m"]["edges"][0]["rest"] == "curve: basis"
    assert "e1@{ animate: true, curve: basis }" in got["once"] and got["stable"]
    plain = _go("flowchart LR\n  A --> B\n")
    assert "@" not in plain["once"]


def test_a_line_for_an_unknown_edge_is_a_node_and_survives():
    got = _go("flowchart LR\n  A --> B\n  zz@{ animate: true }\n")
    assert "zz@{ animate: true }" in got["once"] and got["stable"]


def test_the_menu_entry_is_in_the_lazy_style_file_and_reduced_motion_stops_the_picture():
    style = (ROOT / "frontend/js/diagram-style.js").read_text(encoding="utf-8")
    joins = (ROOT / "frontend/js/diagram-joins.js").read_text(encoding="utf-8")
    draw = (ROOT / "frontend/js/mermaid-draw.js").read_text(encoding="utf-8")
    assert "function animate(" in style and "Moving, quickly" in style and "style.animate(S, h, edge)" in joins
    assert 'dataset.motion === "reduced"' in draw and "prefers-reduced-motion" in draw and "animation:none" in draw
