"""L-documents-59: a markdown string and a line break in a node name are model fields, not kept lines."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_diagram_model import _run

ROOT = Path(__file__).resolve().parents[1]


def _go(src: str):
    body = f"""const m = diagramModel.parse({json.dumps(src)});
const once = diagramModel.print(m);
console.log(JSON.stringify({{ nodes: m.nodes, kept: m.kept, once, stable: diagramModel.print(diagramModel.parse(once)) === once }}));"""
    return _run(body)


def test_a_markdown_string_is_read_into_the_node_and_written_back():
    got = _go('flowchart TD\n  A["`**Bold** and *soft*`"] --> B[Plain]\n')
    assert got["kept"] == []
    a = got["nodes"][0]
    assert a["text"] == "**Bold** and *soft*" and a["md"] is True
    assert "md" not in got["nodes"][1]
    assert 'A["`**Bold** and *soft*`"]' in got["once"] and got["stable"]


def test_turning_markdown_off_writes_a_plain_quoted_label():
    body = """const m = diagramModel.parse('flowchart TD\\n  A["`**x**`"]\\n');
delete m.nodes[0].md;
console.log(JSON.stringify(diagramModel.print(m)));"""
    assert 'A["**x**"]' in _run(body)


def test_a_markdown_text_with_a_quote_is_written_plain_so_the_source_stays_valid():
    body = """const m = diagramModel.parse('flowchart TD\\n  A["`x`"]\\n');
m.nodes[0].text = 'say "hi"';
const out = diagramModel.print(m);
console.log(JSON.stringify({ out, back: diagramModel.parse(out).nodes[0].text }));"""
    got = _run(body)
    assert "`" not in got["out"] and got["back"] == 'say "hi"'


def test_a_br_and_a_newline_in_a_name_are_both_a_line_break():
    got = _go('flowchart TD\n  A["one<br/>two"] --> B\n')
    assert got["nodes"][0]["text"] == "one<br/>two" and got["kept"] == []
    assert 'A["one<br/>two"]' in got["once"] and got["stable"]
    body = """const m = diagramModel.parse('flowchart TD\\n  A[x]\\n');
m.nodes[0].text = 'one\\ntwo';
console.log(JSON.stringify(diagramModel.print(m)));"""
    assert 'A["one<br/>two"]' in _run(body)


def test_the_block_menu_toggles_markdown():
    js = (ROOT / "frontend/js/diagram-builder.js").read_text(encoding="utf-8")
    assert "Markdown text" in js and "Plain text" in js


def test_markdown_text_with_a_br_is_written_plain():
    body = """const m = diagramModel.parse('flowchart TD\\n  A["`x`"]\\n');
m.nodes[0].text = 'a<br/>b';
console.log(JSON.stringify(diagramModel.print(m)));"""
    assert 'A["a<br/>b"]' in _run(body)
