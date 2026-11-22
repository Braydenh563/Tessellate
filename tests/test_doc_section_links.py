"""Source text: the sections block is browser code and lazy CSS with no runner here, so they are read as text.

Labelled and linked sections, and the ```sections block (L-documents-49; DOCUMENTS_PLAN 24 row 10).

The owner: "on long form notes and documents, you can define topics, or use special characters, commands etc to label and
link sections of documents ... visually connect ideas across the current document and link them, with reasons, you can
have a local graph of linked ideas available for the current document and can even embed and render the graph in the
document". A label is a block id (`^name`) on a heading or a paragraph; a link with a reason is `[[#^name|reason]]`
written inside another labelled section. The reader is a pure region run here in node; the wiring is checked by text.
In Chromium: a three-section document with two reasoned links draws 3 nodes and 2 labelled edges (the agent's sweep,
numbers in CHANGELOG).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

DOC = (
    "# Method ^method\n\nWe sampled forty notes.\n\n"
    "# Results ^results\n\nThe counts, see [[#^method|the numbers come from it]].\n\n"
    "A side remark. ^aside\n\n"
    "# Discussion ^discuss\n\nIt follows from [[#^results|it explains the counts]] and [[#^gone]].\n\n"
    "```\n# Not a heading ^fenced\n[[#^method|inside code]]\n```\n"
)


def _run(body: str) -> object:
    text = (JS / "documents-sections.js").read_text(encoding="utf-8")
    region = text[text.index("// DOC-SECTIONS-BEGIN") : text.index("// DOC-SECTIONS-END")]
    script = "(() => {\n" + region + "\nglobalThis.s = { parse, graph, layout, pickBlock };\n})();\nconst s = globalThis.s;\n" + body
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_labels_are_block_ids_on_headings_and_paragraphs_outside_code() -> None:
    got = _run(f"const m = s.parse({json.dumps(DOC)}); console.log(JSON.stringify(m.sections.map((x) => [x.id, x.label, x.kind])));")
    assert got == [
        ["method", "Method", "heading"],
        ["results", "Results", "heading"],
        ["aside", "A side remark.", "paragraph"],
        ["discuss", "Discussion", "heading"],
    ]


@node
def test_links_carry_their_reason_and_the_section_they_are_written_in() -> None:
    got = _run(f"const m = s.parse({json.dumps(DOC)}); console.log(JSON.stringify(m.links.map((l) => [l.from, l.to, l.reason, l.missing])));")
    assert got == [
        ["results", "method", "the numbers come from it", False],
        ["discuss", "results", "it explains the counts", False],
        ["discuss", "gone", "", True],
    ]


@node
def test_a_link_in_a_labelled_paragraph_belongs_to_the_paragraph_and_one_outside_any_section_to_none() -> None:
    text = "Intro [[#^b|why]]\n\n# B ^b\n\nA claim [[#^b|self]] and [[#^p|see it]]. ^p\n"
    got = _run(f"const m = s.parse({json.dumps(text)}); console.log(JSON.stringify(m.links.map((l) => [l.from, l.to])));")
    assert got == [[None, "b"], ["p", "b"], ["p", "p"]]


@node
def test_the_graph_is_the_labelled_sections_and_the_links_between_two_of_them() -> None:
    got = _run(
        f"const g = s.graph(s.parse({json.dumps(DOC)}));"
        "const p = s.layout(g.nodes.length, 480, 300);"
        "console.log(JSON.stringify({ nodes: g.nodes.map((n) => n.id), edges: g.edges.map((e) => [e.from, e.to, e.reason]),"
        " inside: p.every((q) => q.x > 0 && q.x < 480 && q.y > 0 && q.y < 300), apart: new Set(p.map((q) => `${Math.round(q.x)},${Math.round(q.y)}`)).size }));"
    )
    assert got["nodes"] == ["method", "results", "aside", "discuss"]
    # The dangling link (to a label that is not there) draws no edge.
    assert got["edges"] == [["results", "method", "the numbers come from it"], ["discuss", "results", "it explains the counts"]]
    assert got["inside"] is True and got["apart"] == 4


@node
def test_a_long_line_reads_quickly() -> None:
    """CodeQL js/polynomial-redos: the patterns run on every line of a document a person may have pasted from anywhere."""
    got = _run(
        "const t = Date.now(); s.parse('[[#^' + 'a'.repeat(40000) + ' ' + ' '.repeat(40000) + '^x x\\n' + '[[#^a|'.repeat(8000));"
        "console.log(JSON.stringify(Date.now() - t));"
    )
    assert got < 1000


def test_the_block_is_lazy_drawn_in_read_and_live_and_offered_in_the_menus() -> None:
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    docs = documents_text()
    # Registered beside the fence that asks for it, so the boot scripts' gzip total pays nothing.
    assert 'LAZY_MODULES.docSections = ["/css/doc-graph-lazy.css", "/js/documents-sections.js"];' in math
    assert 'module: "docSections"' in math
    assert "docMathRender.sectionsIn(preview);" in docs and "docMathRender.sectionsField(CM)" in docs
    # The "/" menu and the palette both insert it.
    assert '{ id: "sections"' in (JS / "editor.js").read_text(encoding="utf-8")
    assert '{ id: "insert-sections"' in docs and "```sections" in docs
    # The outline's facts pass asks for the Section links list, which loads the module only when a link is written.
    assert "docMathRender.sections.links(" in docs
    sections = (JS / "documents-sections.js").read_text(encoding="utf-8")
    for banned in ("eval(", "new Function", "innerHTML", "insertAdjacentHTML"):
        assert banned not in sections, banned
    # The module adds no global name: everything is on `docMathRender.sections`.
    assert "Object.assign(window" not in sections


def test_the_guide_has_a_topic_and_a_lead_for_sections() -> None:
    from tessellate.ai import help_chat, help_leads

    topics = {t["id"]: t for t in help_chat.HELP_TOPICS}
    assert "document-sections" in topics and len(topics["document-sections"]["body"]) < 1900
    assert "[[#^" in topics["document-sections"]["body"] and "Section links" in topics["document-sections"]["body"]
    assert "document-sections" in help_leads.TOPIC_LEADS


@node
def test_a_section_is_the_last_read_block_stamped_at_or_before_its_line() -> None:
    # L-documents-114: the title the preview prepends is the shift; no block before the line is -1.
    got = _run(
        'console.log(JSON.stringify([s.pickBlock(["2","4","8"], 2, 3), s.pickBlock(["2","4","8"], 2, 0),'
        ' s.pickBlock(["2","4","8"], 2, 99), s.pickBlock(["2","4","8"], 0, 1), s.pickBlock([], 0, 5)]))'
    )
    assert got == [1, 0, 2, -1, -1]


def test_a_link_or_node_pressed_in_read_stays_in_read_and_rings_the_block() -> None:
    # L-documents-114: no switch to Live from Read; the rendered block gets the jump-to ring.
    sections = (JS / "documents-sections.js").read_text(encoding="utf-8")
    assert 'setDocView("live")' not in sections
    assert "flashRevealed(el)" in sections and "readBlock(" in sections
    # Outside Read the block reference's own reveal still selects the block.
    assert "return docRevealBlock(id);" in sections


def test_hover_and_focus_peek_both_sections_without_moving_the_caret() -> None:
    # L-documents-115: a marker class on the rendered blocks and a decoration on the lines; no selection dispatch.
    sections = (JS / "documents-sections.js").read_text(encoding="utf-8")
    peek = sections[sections.index("function peek(ids)") : sections.index("//: Hover and focus on one element")]
    assert "selection" not in peek and "scrollIntoView" not in peek and ".focus(" not in peek
    for event in ("mouseenter", "mouseleave", "focusin", "focusout"):
        assert f'"{event}"' in sections
    # A row, an edge and a node all peek.
    assert sections.count("peekOn(") == 4  # the definition and the three callers
    css = (ROOT / "frontend" / "css" / "doc-graph-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index("#doc-preview .dsec-peek") :]
    rule = rule[: rule.index("}")]
    assert "outline: 2px solid var(--accent)" in rule and "animation" not in rule and ".cm-line.dsec-peek" in rule


def test_the_guide_says_hover_shows_both_sections_and_read_stays_read() -> None:
    from tessellate.ai import help_chat

    body = {t["id"]: t for t in help_chat.HELP_TOPICS}["document-sections"]["body"]
    assert "hover" in body.lower() and "Read" in body and len(body) < 1900
