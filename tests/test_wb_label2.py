"""F2, draw.io's second label on an edge: a connector carries `label2` beside its label, at `label2_t` along the line
(0.85 until moved), with the first label's look. Format sets it, Find and Replace all read it and Shift+Delete clears it.

The module runs in node against a small stand-in for the page; the board's own functions are named in the last test."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    # A minimal SVG: a group holds children by class, and a text node keeps its attributes and style.
    stand_in = """
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.style = {}; this.children = []; this.textContent = ""; this.dataset = {};
    const owner = this; this.classList = { toggle: (c, on) => { const set = new Set((owner.attrs.class || "").split(/\\s+/).filter(Boolean)); on ? set.add(c) : set.delete(c); owner.attrs.class = [...set].join(" "); } }; }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  appendChild(c) { c.parent = this; this.children.push(c); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  querySelector(sel) {
    const want = sel.replace(":scope > ", "").replace(/^\\./, "");
    return this.children.find((c) => (c.attrs.class || "").split(/\\s+/).includes(want)) || null;
  }
}
const document = { createElementNS: (ns, tag) => new El(tag), getElementById: () => null };
const wbFmtState = {}; const onSurface = () => {};
const wbLinkTakesLabel = (sketch, parsed) => String(parsed?.type || "").startsWith("link-");
const wbExpandPlaceholders = (text) => text; const wbPlaceholderBuiltins = () => null;
const wbLinkMidpoint = (d, t) => (d ? { x: 100 * t, y: 50 } : null);
"""
    script = stand_in + frontend_text("whiteboard-draw-more.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_second_label_sits_near_the_end_until_it_is_moved():
    got = _node(
        "const m = wbFmtState.drawMore;"
        "console.log(JSON.stringify([m.label2T({}), m.label2T({ label2_t: 0.2 }), m.label2T({ label2_t: 7 }), m.label2T({ label2_t: 'x' })]));"
    )
    assert got == [0.85, 0.2, 0.85, 0.85]


def test_painting_adds_one_text_with_the_connectors_label_look_and_clears_it_when_the_words_go():
    got = _node(
        "const m = wbFmtState.drawMore;"
        "const group = new El('g'); group.children.push(Object.assign(new El('path'), { attrs: { class: 'sketch-hitbox', d: 'M0 0 L100 0' } }));"
        "group.querySelector = function (sel) { return sel === '.sketch-hitbox' ? this.children[0] : El.prototype.querySelector.call(this, sel); };"
        "const link = { type: 'link-curved', label2: ' to ', label_size: 20, label_bold: true, label_color: '#c00', label_chip: true };"
        "m.paintLabel2(group, {}, link); m.paintLabel2(group, {}, link);"
        "const t = group.children.filter((c) => c.tag === 'text');"
        "const out = { count: t.length, text: t[0].textContent, cls: t[0].attrs.class, x: t[0].attrs.x, y: t[0].attrs.y, size: t[0].style.fontSize, weight: t[0].style.fontWeight, fill: t[0].style.fill };"
        "m.paintLabel2(group, {}, { ...link, label2: undefined });"
        "out.after = group.children.filter((c) => c.tag === 'text').length;"
        "console.log(JSON.stringify(out));"
    )
    #: Painted twice, still one text; the words are trimmed; 0.85 of the 100-long line is x 85.
    assert got["count"] == 1 and got["text"] == "to" and got["x"] == "85" and got["y"] == "50"
    assert "wb-link-label" in got["cls"].split() and "wb-link-label2" in got["cls"].split() and "wb-link-label-chip" in got["cls"].split()
    assert (got["size"], got["weight"], got["fill"]) == ("20px", "700", "#c00")
    assert got["after"] == 0


def test_a_shape_or_a_plain_line_gets_no_second_label():
    got = _node(
        "const m = wbFmtState.drawMore; const group = new El('g');"
        "m.paintLabel2(group, {}, { type: 'shape', label2: 'x' }); m.paintLabel2(group, {}, { type: 'link-straight' });"
        "console.log(JSON.stringify(group.children.length));"
    )
    assert got == 0


def test_the_first_labels_lookups_leave_the_second_alone():
    for name in ("wbLayoutLinkLabel", "wbPaintLinkLabel"):
        assert ':not(.wb-link-label2)' in _function(name), name
    assert 'wbFmtState.drawMore?.layoutLabel2(groupEl);' in _function("wbLayoutLinkLabel")
    assert 'wbFmtState.drawMore?.paintLabel2(groupEl, sketch, parsed);' in _function("wbPaintLinkLabel")
    assert ':scope > .wb-link-label:not(.wb-link-label2)")?.getBBox()' in WB


def test_find_and_replace_all_read_the_second_label_too():
    assert 'data?.label2 ? `\\n${data.label2}` : ""' in _function("wbSearchTextFor")
    replace = _function("wbBoardReplaceAll")
    assert 'wbReplaceText(own.label2, needle, to, wbBoardSearch)' in replace and "note.count + second.count" in replace
    assert "second?.count ? { label2: second.text }" in _function("wbReplaceWrite")


def test_the_panel_the_rows_and_the_help_agree():
    fmt = script_file_text("whiteboard-format.js")
    assert '"tip", "loop", "label2", "label2-t"],' in fmt
    assert 'case "label2": return typeof s?.label2 === "string" ? s.label2 : "";' in fmt
    assert '["wb-fmt-label2", "label2", "label2"], ["wb-fmt-label2-t", "label2-t", "label2-t"]' in fmt
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-fmt="label2"' in html and 'id="wb-fmt-label2"' in html and 'data-fmt="label2-t"' in html and 'id="wb-fmt-label2-t"' in html
    assert "<b>Second label, Second label along</b>" in html
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
