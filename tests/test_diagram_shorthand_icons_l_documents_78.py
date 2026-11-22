"""L-documents-78: `:::class` shorthand and `@{ icon }` nodes are the model's own; a linked node on a document's picture is a hit area."""

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


def test_the_shorthand_after_an_id_or_a_shape_is_the_nodes_class():
    got = _go("flowchart TD\n  A:::hot --> B[Text]:::hot\n  C\n  classDef hot fill:#f96\n")
    nodes = {n["id"]: n for n in got["m"]["nodes"]}
    assert nodes["A"]["cls"] == "hot" and nodes["B"]["cls"] == "hot" and nodes["B"]["text"] == "Text" and "cls" not in nodes["C"]
    assert len(got["m"]["edges"]) == 1 and got["kept"] == []


def test_the_shorthand_prints_as_a_class_line_and_is_stable():
    got = _go("flowchart TD\n  A:::hot --> B\n  classDef hot fill:#f96\n")
    assert "  class A hot" in got["once"].splitlines() and ":::" not in got["once"] and got["stable"]


def test_a_shorthand_class_that_nothing_defines_stays_a_kept_class_line():
    got = _go("flowchart TD\n  A:::ghost --> B\n")
    assert got["kept"] == ["class A ghost"] and "cls" not in got["m"]["nodes"][0] and got["stable"]
    assert "class A ghost" in got["once"]


def test_an_icon_node_is_drawn_with_its_label_and_its_line_prints_back():
    src = 'flowchart TD\n  A@{ icon: "fa:user", label: "Ada", form: "square" } --> B\n'
    got = _go(src)
    nodes = {n["id"]: n for n in got["m"]["nodes"]}
    assert nodes["A"]["text"] == "Ada" and nodes["A"]["meta"] == 'icon: "fa:user", label: "Ada", form: "square"'
    assert got["kept"] == [] and len(got["m"]["edges"]) == 1
    assert 'A@{ icon: "fa:user", label: "Ada", form: "square" }' in got["once"].splitlines()[2] or any(
        line.strip() == 'A@{ icon: "fa:user", label: "Ada", form: "square" }' for line in got["once"].splitlines()
    )
    assert got["stable"]


def test_renaming_an_icon_node_rewrites_its_label_only():
    body = """const m = diagramModel.parse('flowchart TD\\n  A@{ icon: "fa:user", label: "Ada" }\\n');
m.nodes[0].text = 'Grace $& x';
console.log(JSON.stringify(diagramModel.print(m)));"""
    out = _run(body)
    assert 'icon: "fa:user"' in out and 'label: "Grace $& x"' in out


def test_the_picture_gets_a_hit_layer_for_linked_nodes_through_the_document_link_path():
    draw = (ROOT / "frontend/js/mermaid-draw.js").read_text(encoding="utf-8")
    assert "mermaidShow.links" in draw and "docOpenLink(" in draw and "docOpenWikiTarget(" in draw
    assert "window.open" not in draw.split("mermaidShow.links")[1].split("function mermaidFill(")[0]
    css = (ROOT / "frontend/css/mermaid-lazy.css").read_text(encoding="utf-8")
    assert ".md-mermaid-hit" in css


def test_the_help_says_icons_are_kept_not_drawn():
    help_ = (ROOT / "src/tessellate/ai/help_topics_more.py").read_text(encoding="utf-8")
    assert ":::" in help_ and "icon" in help_.lower()


def test_the_frame_declares_xlink_so_a_click_link_does_not_break_the_picture():
    frame = (ROOT / "frontend/js/mermaid-frame.js").read_text(encoding="utf-8")
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in frame and "/\\bxlink:/.test(svgText)" in frame
