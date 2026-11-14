"""INBOX 1661 step B (first slice): block colour in the model, the colour and shortcuts sheets (diagram-style.js)."""

import json
import re
from pathlib import Path

from tests.test_diagram_model import _run

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
STYLE = (JS / "diagram-style.js").read_text(encoding="utf-8")
BAR = (JS / "diagram-bar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
PALETTE = {
    "red": "#da5252", "orange": "#ba6d36", "amber": "#9e7c17", "lime": "#6d8a14", "green": "#15952b", "teal": "#159172",
    "cyan": "#178ca3", "blue": "#387fe3", "indigo": "#6a74ea", "violet": "#9b63e9", "magenta": "#d332e2", "pink": "#ce5591",
}


def test_the_builders_own_style_line_lifts_into_a_fill_and_prints_back_byte_for_byte():
    body = """
const m = diagramModel.parse('flowchart TD\\n  A["x"] --> B["y"]\\n');
m.nodes[1].fill = '#387fe3';
const once = diagramModel.print(m);
const back = diagramModel.parse(once);
console.log(JSON.stringify({ once, fill: back.nodes[1].fill, kept: back.kept.length, again: diagramModel.print(back) === once }));
"""
    got = _run(body)
    assert got["once"].endswith("  style B fill:#cddff8,stroke:#387fe3,color:#1a1a1a\n")
    assert got["fill"] == "#387fe3" and got["kept"] == 0 and got["again"] is True


def test_a_foreign_style_classdef_or_class_line_stays_kept_verbatim():
    src = "flowchart TD\n  A --> B\n  style A fill:#f9f,stroke:#333\n  classDef hot fill:#fff\n  class B hot\n  style B fill:#aaaaaa,stroke:#387fe3,color:#1a1a1a\n"
    body = f"const m = diagramModel.parse({json.dumps(src)}); console.log(JSON.stringify({{ out: diagramModel.print(m), fills: m.nodes.map((n) => n.fill || null) }}));"
    got = _run(body)
    for line in ("style A fill:#f9f,stroke:#333", "classDef hot fill:#fff", "class B hot", "style B fill:#aaaaaa,stroke:#387fe3,color:#1a1a1a"):
        assert line in got["out"]
    # The last line has a tint that is not the builder's, so it is not lifted either.
    assert got["fills"] == [None, None]


def test_a_node_without_a_fill_prints_no_style_line_and_the_twelve_hues_read_on_both_grounds():
    body = "const m = diagramModel.parse('flowchart TD\\n A --> B\\n'); console.log(JSON.stringify(diagramModel.print(m)));"
    assert "style" not in _run(body)

    def lum(hex_):
        c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def ratio(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    for name, hue in PALETTE.items():
        tint = "#" + "".join(f"{round(int(hue[i : i + 2], 16) * 0.25 + 191.25):02x}" for i in (1, 3, 5))
        assert ratio("#1a1a1a", tint) >= 4.5, name
        # The stroke is drawn against the tint (the node's own ground), which is light in both themes.
        assert ratio(hue, tint) >= 2.0, name


def test_the_sheets_are_lazy_and_read_the_key_table():
    assert "diagramStyle: [\"/js/diagram-style.js\"]" in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert "diagramModel.keys" in STYLE and "swatchPicker(" in STYLE and "openSheet(" in STYLE
    # Every key the sheet lists comes from the table; none is typed twice.
    assert not re.search(r"\b(Box|Rounded|Decision)\b.*\b[1-7]\b", STYLE)
    assert "diagramModel.style" in BUILDER and '"?"' in BUILDER
    assert "Keyboard shortcuts" in BUILDER


def test_a_duplicate_keeps_the_colour():
    from tests.test_diagram_builder import _script

    got = _script("flowchart TD\n  A[One]\n", "m.nodes[0].fill = '#387fe3'; const r = o.duplicate(m, ['n:A']); return [r.keys, m.nodes.map((n) => n.fill)];")
    assert got["result"][1] == ["#387fe3", "#387fe3"]


def test_the_shape_keys_work_from_the_picture_and_the_toolbar_and_the_menu_shows_them_as_keys():
    # The review of 1661 B: the keys were heard only by a focused block, and the menu rows put the key in the label.
    assert "rootKey" in BAR and "diagramModel.bar.rootKey" in BUILDER
    assert 'keys: hintOf(shape)' in BAR and '"N or 1"' in BAR
    selects = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    assert 'kbd' in selects and "aria-keyshortcuts" in selects


def test_the_blocks_list_can_be_hidden_and_the_choice_is_kept():
    # Moved by 1661 m: the toolbar's list button became the panel's own fold (diagram-split.js), kept in `diagram.fold`.
    split = (JS / "diagram-split.js").read_text(encoding="utf-8")
    assert "dgm-outline-toggle" not in BAR and 'const FOLD = "diagram.fold"' in split
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert ".dgm-body.dgm-fold-left > :is(.dgm-listcol, .dgm-split-handle)" in css


def test_blind_test_fixes_phone_toolbar_empty_steps_caret_menu_and_new_block_shape():
    # Blind test of 0931c35 (measured at 390 and 1440): the toolbar was 338 px in 306, the empty steps sat under the foot,
    # the shape menu opened at the window's left edge, and a block made from Connect to a decision was a decision.
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert ".dgm-picture.dgm-picture-empty" in css
    assert "r.right, r.bottom, caret" in BAR
    joins = (JS / "diagram-joins.js").read_text(encoding="utf-8")
    assert 'after: key, from, shape: "rect"' in joins


def test_an_arrow_takes_a_colour_from_the_swatch_picker_and_both_ways_is_a_seventh_kind():
    """1679 slice 10: Colour… on the connector menu (lazy style file, one commit), Both ways beside the six kinds, drawn."""
    joins = (JS / "diagram-joins.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert "function edge(S, h, link)" in STYLE and "diagramModel.style = { colour, edge, animate, shortcuts, items }" in STYLE
    assert "swatchPicker(" in STYLE[STYLE.index("function edge(") : STYLE.index("function shortcuts")]
    assert 'label: "ph:palette Colour…"' in joins and "diagramModel.style.edge(S, h, edge)" in joins
    assert '["solid", true, "Both ways", true]' in joins and "diagramModel.joins = { items, pick, ask, go }" in joins
    assert '.dgm-link[data-arrow="both"]::before' in css
