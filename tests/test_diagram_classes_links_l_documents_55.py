"""L-documents-55: classDef, class and click are the model's own (classes, n.cls, n.href); unsafe targets stay kept."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_diagram_model import _run

ROOT = Path(__file__).resolve().parents[1]
SRC = (
    'flowchart TD\n  A --> B\n  C\n  class A,B hot\n  classDef hot fill:#f96,stroke:#333,stroke-width:2px\n'
    '  click A "https://example.com/x" "Open it"\n  click B href "[[Plan]]"\n  click C "javascript:alert(1)"\n  click C callback\n'
    "  classDef default fill:#eee\n"
)


def _go(src: str):
    body = f"""const m = diagramModel.parse({json.dumps(src)});
const once = diagramModel.print(m);
console.log(JSON.stringify({{ m, kept: m.kept.map((k) => k.line), once, stable: diagramModel.print(diagramModel.parse(once)) === once }}));"""
    return _run(body)


def test_class_defs_assignments_and_safe_links_are_lifted():
    got = _go(SRC)
    assert got["m"]["classes"] == [{"name": "hot", "css": "fill:#f96,stroke:#333,stroke-width:2px"}]
    nodes = {n["id"]: n for n in got["m"]["nodes"]}
    assert nodes["A"]["cls"] == "hot" and nodes["B"]["cls"] == "hot" and "cls" not in nodes["C"]
    assert nodes["A"]["href"] == "https://example.com/x" and nodes["A"]["tip"] == "Open it"
    assert nodes["B"]["href"] == "[[Plan]]"


def test_a_javascript_link_a_callback_and_the_default_class_stay_kept_lines():
    got = _go(SRC)
    assert got["kept"] == ['click C "javascript:alert(1)"', "click C callback", "classDef default fill:#eee"]
    assert "href" not in {k for n in got["m"]["nodes"] if n["id"] == "C" for k in n}


def test_they_print_back_in_one_canonical_form_and_are_stable():
    got = _go(SRC)
    lines = got["once"].splitlines()
    assert "  classDef hot fill:#f96,stroke:#333,stroke-width:2px" in lines
    assert "  class A,B hot" in lines
    assert '  click A "https://example.com/x" "Open it"' in lines and '  click B "[[Plan]]"' in lines
    assert got["stable"]


def test_an_unsafe_href_set_in_the_model_is_never_written():
    body = """const m = diagramModel.parse('flowchart TD\\n  A\\n');
m.nodes[0].href = 'javascript:alert(1)';
console.log(JSON.stringify(diagramModel.print(m)));"""
    assert "click" not in _run(body)


def test_the_block_menu_has_class_and_link_and_the_link_opens_through_the_document_link_path():
    style = (ROOT / "frontend/js/diagram-style.js").read_text(encoding="utf-8")
    assert "Class…" in style and "Link…" in style and "Open link" in style
    assert "docOpenLink(href)" in style and "docOpenWikiTarget(" in style and "window.open" not in style
