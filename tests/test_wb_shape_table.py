"""The JS-drawn shape classes (WHITEBOARD_PLAN section 11): `wbFmtState.shapeTable.shapePath(kind, w, h)` in
`whiteboard-shape-table.js`, run in node. Every outline is M, L, C and Z only, fills its box exactly (so a resize that draws it
again keeps the box), and the draw.io words round-trip. The browser half is `scratchpad/ui-sweeps/wbtext3.js`."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

BBOX = """
const bbox = (d) => { const t = d.match(/[MLCZ]|-?\\d*\\.?\\d+/g); let i = 0, x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  const see = (x, y) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); };
  while (i < t.length) { const c = t[i++]; if (c === 'Z') continue; const n = c === 'C' ? 3 : 1; for (let k = 0; k < n; k++) see(+t[i++], +t[i++]); }
  return { minX: x0, minY: y0, maxX: x1, maxY: y1 }; };
const move = (d, { dx, dy }) => { const t = d.match(/[MLCZ]|-?\\d*\\.?\\d+/g); const out = []; let k = 0;
  for (const c of t) { if (/[MLCZ]/.test(c)) { out.push(c); k = 0; } else { out.push(+c + (k % 2 ? dy : dx)); k++; } } return out.join(' '); };
"""


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {};\n" + frontend_text("whiteboard-shape-table.js") + "\n" + BBOX + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_table_holds_the_plans_forty_kinds_and_every_one_draws():
    out = _node("const t = wbFmtState.shapeTable; console.log(JSON.stringify(t.kinds.map((k) => [k, t.shapePath(k, 160, 100)])));")
    assert len(out) == 40
    for kind, d in out:
        assert d and set(d.replace(".", "").replace("-", "")) <= set("MLCZ 0123456789"), kind
        assert "NaN" not in d, kind


def test_each_outline_fills_its_box_exactly_at_several_sizes():
    rows = _node(
        "const t = wbFmtState.shapeTable; const out = [];"
        "for (const k of t.kinds) for (const [w, h] of [[160, 100], [40, 300], [300, 40], [1, 1]]) { const b = bbox(t.shapePath(k, w, h));"
        "out.push([k, w, h, b.minX, b.minY, b.maxX, b.maxY]); } console.log(JSON.stringify(out));"
    )
    for kind, w, h, x0, y0, x1, y1 in rows:
        assert (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)) == (0, 0, w, h), (kind, w, h, x0, y0, x1, y1)


def test_an_unknown_kind_is_null():
    assert _node("console.log(JSON.stringify(wbFmtState.shapeTable.shapePath('nope', 10, 10)));") is None


def test_a_resize_draws_the_outline_again_and_keeps_the_corner_size():
    out = _node(
        "const t = wbFmtState.shapeTable; const old = move(t.shapePath('step', 160, 80), { dx: 50, dy: 20 });"
        # what the board's stretch makes: every x about the left edge times 2.5
        "let k = 0; const stretched = old.replace(/-?\\d*\\.?\\d+/g, (n) => ((k++ % 2) ? n : 50 + (n - 50) * 2.5));"
        "const next = t.afterResize('step', old, stretched, bbox, move);"
        "console.log(JSON.stringify([bbox(next), next === move(t.shapePath('step', 400, 80), { dx: 50, dy: 20 }), stretched === next]));"
    )
    box, same, kept_stretch = out
    assert box == {"minX": 50, "minY": 20, "maxX": 450, "maxY": 100}
    # the notch is a share of the height (40 at h = 80), so it stays 40 at any width; a plain stretch would have made it 100
    assert same and not kept_stretch


def test_an_edited_or_turned_outline_is_left_as_the_board_stretched_it():
    out = _node(
        "const t = wbFmtState.shapeTable; const edited = t.shapePath('step', 160, 80).replace('0 0 L', '3 0 L');"
        "console.log(JSON.stringify(t.afterResize('step', edited, edited, bbox, move)));"
    )
    assert out is None


def test_draw_io_words_round_trip():
    out = _node(
        "const t = wbFmtState.shapeTable; const ks = t.kinds.map((k) => { const w = t.toDrawio(k); const style = {}; for (const p of w.split(';')) { const [a, b] = p.split('='); if (a) style[a] = b; }"
        "return [k, t.fromDrawio(style)]; }); console.log(JSON.stringify(ks));"
    )
    for kind, back in out:
        # pentagon and octagon use draw.io's mxgraph stencil names; every kind reads back as itself
        assert back == kind, (kind, back)


def test_draw_io_cylinder3_south_is_a_tube_and_an_unknown_word_is_empty():
    assert _node("console.log(JSON.stringify([wbFmtState.shapeTable.fromDrawio({ shape: 'cylinder3', direction: 'south' }), wbFmtState.shapeTable.fromDrawio({ shape: 'cylinder3' }), wbFmtState.shapeTable.fromDrawio({ shape: 'x' })]));") == ["tube", "cylinder", ""]


def test_the_library_set_file_is_what_the_table_makes():
    from pathlib import Path

    made = _node("console.log(JSON.stringify(wbFmtState.shapeTable.setFile()));")
    root = Path(__file__).resolve().parents[1] / "frontend" / "board-library"
    assert json.loads((root / "shapes-js.json").read_text(encoding="utf-8")) == made, (
        "regenerate: node -e with whiteboard-shape-table.js, write setFile() to frontend/board-library/shapes-js.json")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))["sets"]
    assert {"key": "shapes-js", "name": "Drawn shapes", "count": len(made["items"])} in index
    assert len(made["items"]) >= 20
    for item in made["items"]:
        data = item["payload"]["items"][0]["data"]
        assert data["shapeKind"] == item["key"] and data["shape"] == "custom" and "Z" in data["d"], item["name"]


def test_it_is_wired_into_the_board_the_resize_and_draw_io():
    assert "/js/whiteboard-shape-table.js" in frontend_text("lazy-entries.js")
    wb = frontend_text("whiteboard.js")
    assert wb.count("shapeTable?.resized(") == 3
    interchange = frontend_text("whiteboard-interchange.js")
    for needle in ("shapeTable?.fromDrawio(", "shapeTable?.toDrawio("):
        assert needle in interchange
    assert "innerHTML" not in frontend_text("whiteboard-shape-table.js")
