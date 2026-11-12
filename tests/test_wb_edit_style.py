"""Edit style as text (draw.io's Edit Style, Ctrl+E; WHITEBOARD_PLAN "The draw.io
programme" section 1): the Data tab shows one item's style as JSON; Apply
validates it and writes it as one undo step. The item's geometry, connection and
content stay out of the text, so a typo cannot detach a connector or empty a box."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _kit() -> str:
    start = FMT.index("//: **Edit style as text**")
    return "const wbFmtState = {};\nconst WB_OBJECT_STYLE_KEYS = ['color', 'bg', 'border_color', 'font_size'];\n" + FMT[start : FMT.index("//: --- end edit style", start)]


def test_the_text_leaves_out_what_is_not_style_and_parse_keeps_it():
    script = _kit() + """
const raw = wbFmtState.raw;
const sketch = { d: "M0 0 L1 1", type: "line", color: "#111111", width: 3, props: { a: 1 }, sourceId: 4 };
const text = raw.show("sketch", sketch);
const link = { type: "link-arrow", sourceId: 4, targetId: 5, color: "#222222", flow: true };
const box = { text: "hello", color: "#333333", bg: "#ffee00", bold: true };
console.log(JSON.stringify({
  text,
  link: raw.show("sketch", link),
  box: raw.show("object", box),
  ok: raw.parse("sketch", sketch, '{"color": "#ff0000", "round": 8}'),
  dropsKeys: raw.parse("sketch", sketch, '{"width": 4}'),
  protectedIgnored: raw.parse("sketch", sketch, '{"d": "M9 9", "type": "link-x", "color": "#000000"}'),
  notJson: raw.parse("sketch", sketch, '{color'),
  array: raw.parse("sketch", sketch, '[1]'),
  tooBig: raw.parse("sketch", sketch, JSON.stringify({ color: "x".repeat(9000) })),
  deep: raw.parse("sketch", sketch, '{"color": {"a": {"b": {"c": 1}}}}'),
  objectOk: raw.parse("object", box, '{"bg": "#000000", "bold": false}'),
}));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert json.loads(out["text"]) == {"color": "#111111", "width": 3}
    assert json.loads(out["link"]) == {"color": "#222222", "flow": True}
    assert json.loads(out["box"]) == {"color": "#333333", "bg": "#ffee00", "bold": True}
    # Keys in the text are set; keys taken out of it are removed (null in the patch); nothing protected moves.
    assert out["ok"] == {"patch": {"color": "#ff0000", "round": 8, "width": None}}
    assert out["dropsKeys"] == {"patch": {"width": 4, "color": None}}
    assert out["protectedIgnored"] == {"patch": {"color": "#000000", "width": None}}
    assert out["notJson"]["error"] and out["array"]["error"] and out["tooBig"]["error"] and out["deep"]["error"]
    assert out["objectOk"] == {"patch": {"bg": "#000000", "bold": False, "color": None}}


def test_the_data_tab_has_the_box_and_the_panel_wires_it():
    data = HTML[HTML.index('data-format-panel="data"'):]
    assert 'id="wb-fmt-raw"' in data and 'id="wb-fmt-raw-apply"' in data and 'id="wb-fmt-raw-status"' in data
    assert 'data-fmt="rawstyle"' in data
    for kind in ("shape", "line", "arrow", "link", "text"):
        row = FMT[FMT.index(f"  {kind}: ["):].split("\n", 1)[0]
        assert '"rawstyle"' in row, kind
    assert 'on("wb-fmt-raw-apply", "click"' in FMT
    assert 'wbFmtApply("rawstyle"' in FMT
