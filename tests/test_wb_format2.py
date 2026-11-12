"""Board format, round two (WHITEBOARD_PLAN, wbformat2): picture border, grid size and colour, board options,
paper size, PNG and HTML export, rulers and units.

The server half runs through the API; the pure writers and readers run in node against the source."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERCHANGE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")


def app_js_text() -> str:
    """The whiteboard's scripts (they load apart from the app's boot scripts, so `tests/_app_js.py` does not hold them)."""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "js").glob("whiteboard*.js")))


def _node(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout.strip()


def _board(client, kind="board"):
    return client.post("/whiteboard/boards", json={"name": "Format two", "type": kind}).json()


def _pure_interchange() -> str:
    return INTERCHANGE[: INTERCHANGE.index("//: The rows inside an SVG")]


# --- 1. Picture border ------------------------------------------------------------------------------------


def test_a_picture_border_round_trips_and_its_width_is_bounded(ai_client):
    data = {"url": "/media/a.png", "border_color": "#112233", "border_width": 3}
    made = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": data, "x": 0, "y": 0, "width": 80, "height": 60})
    assert made.status_code == 201, made.text
    stored = ai_client.get("/whiteboard/").json()["objects"][0]["data"]
    assert (stored["border_color"], stored["border_width"]) == ("#112233", 3)
    too_wide = ai_client.post("/whiteboard/objects", json={"kind": "image", "data": {**data, "border_width": 99}, "x": 0, "y": 0, "width": 80, "height": 60})
    assert too_wide.status_code == 422


def test_a_picture_border_has_format_fields_a_render_and_an_export():
    js = app_js_text()
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-fmt="imageborder"' in html and 'id="wb-fmt-ibcolor"' in html and 'id="wb-fmt-ibwidth"' in html
    assert '"imageborder"' in js and "border_width" in js
    # Drawn on the board as an outline, and in the export as a stroked path over the picture.
    assert "obj.data.border_width" in js and "outlineOffset" in js


def test_a_picture_border_survives_a_drawio_round_trip():
    state = {"nodes": [], "sketches": [], "objects": [
        {"id": 1, "kind": "image", "x": 10, "y": 20, "width": 120, "height": 80, "z": 1, "data": {"url": "/media/a.png", "border_color": "#aa0011", "border_width": 4}}]}
    out = json.loads(_node(_pure_interchange() + f"\nconsole.log(JSON.stringify(wbBoardToDrawio({json.dumps(state)}, {{ box: () => null }})));"))
    xml = out["xml"]
    assert "shape=image" in xml and "imageBorder=#aa0011" in xml and "strokeWidth=4" in xml and "image=/media/a.png" in xml
    assert out["skipped"].get("pictures") is None
    style = "shape=image;image=/media/a.png;imageBorder=#aa0011;strokeWidth=4;"
    cells = [{"id": "0"}, {"id": "1", "parent": "0"}, {"id": "2", "parent": "1", "vertex": True, "style": style, "value": "", "geo": {"x": 10, "y": 20, "width": 120, "height": 80}}]
    plan = json.loads(_node(_pure_interchange() + f"\nconsole.log(JSON.stringify(wbDrawioPlan({json.dumps(cells)}).items));"))
    assert plan[0]["kind"] == "image" and plan[0]["url"] == "/media/a.png"
    assert plan[0]["look"] == {"border_color": "#aa0011", "border_width": 4}


# --- 2. Grid size and colour ------------------------------------------------------------------------------


def test_a_boards_grid_size_and_colour_are_kept_on_the_board(ai_client):
    board = _board(ai_client)
    out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"grid_size": 40, "grid_color": "#AA3300"}})
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"grid_size": 40, "grid_color": "#aa3300"}
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    assert state["background"] == {"grid_size": 40, "grid_color": "#aa3300"}
    # 24 is the default, so it is not stored; a patch of one field keeps the other.
    back = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"grid_size": 24}}).json()
    assert back["background"] == {"grid_color": "#aa3300"}
    cleared = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"grid_color": None}})
    assert cleared.json()["background"] == {}


def test_a_grid_size_out_of_range_or_a_bad_colour_is_refused(ai_client):
    board = _board(ai_client)
    for patch in ({"grid_size": 2}, {"grid_size": 500}, {"grid_color": "red"}, {"grid_color": "url(x)"}):
        refused = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": patch})
        assert refused.status_code == 422


def test_snap_nudge_and_the_grid_all_read_the_boards_grid_setting():
    js = app_js_text()
    # One value, assigned from the board's settings, that every reader already uses.
    assert "let WB_GRID_SPACING = 24;" in js and "WB_GRID_SPACING = bg.grid_size || 24;" in js
    assert 'el.style.setProperty("--wb-grid-ink", bg.grid_color)' in js
    assert "wbSyncGridToTransform();\n  wbFmtState.opts?.sync(bg);" in js
    # Snap, the Shift+arrow nudge and the drawn grid size are the same constant, not a second number.
    assert "Math.round(value / WB_GRID_SPACING) * WB_GRID_SPACING" in js
    assert "const step = e.shiftKey ? (wbSnapOn() ? WB_GRID_SPACING : 10) : 1;" in js
    assert '`${WB_GRID_SPACING * t.k}px`' in js
    # Undo of a background change restores the grid too.
    assert '"grid_size", "grid_color"' in js


def test_the_board_section_of_the_format_panel_has_the_grid_fields_and_help():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-board-options"' in html and 'id="wb-bo-grid-size"' in html and 'id="wb-bo-grid-color"' in html
    assert 'data-help-for="wb-fmt-help-boardopts"' in html
    assert "/js/whiteboard-options.js" in (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")


# --- 3. Guides, page view and the shadow default ------------------------------------------------------------


def _pdf_source() -> str:
    """The `wbPdf` module on its own: it needs nothing from the page."""
    start = INTERCHANGE.index("const wbPdf = (() => {")
    return INTERCHANGE[start : INTERCHANGE.index("\n})();", start) + 6]


def test_a_boards_switches_store_only_their_non_default_value(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    out = ai_client.put(url, json={"background": {"guides": False, "page_view": True, "shadow_default": True}})
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"guides": False, "page_view": True, "shadow_default": True}
    # The default values clear the setting, they are not stored.
    back = ai_client.put(url, json={"background": {"guides": True, "page_view": False}})
    assert back.json()["background"] == {"shadow_default": True}
    cleared = ai_client.put(url, json={"background": {"shadow_default": None}})
    assert cleared.json()["background"] == {}


def test_the_switches_are_read_by_guides_new_shapes_and_the_page_frames():
    js = app_js_text()
    assert "if (wbBoardBackground().guides === false) return [];" in js
    assert 'bg.shadow_default && (group === "shape" || group === "text")' in js
    assert '"guides", "page_view", "shadow_default"' in js
    options = (ROOT / "frontend" / "js" / "whiteboard-options.js").read_text(encoding="utf-8")
    assert "wbPdf.pagePx(bg)" in options and 'class", "wb-page-frame"' in options
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for ident in ("wb-bo-guides", "wb-bo-pageview", "wb-bo-shadow"):
        assert f'id="{ident}"' in html


def test_the_page_size_in_board_units_comes_from_the_one_size_table():
    out = _node(_pdf_source() + ' console.log(JSON.stringify([...wbPdf.pagePx({}), ...wbPdf.pagePx({ orientation: "landscape" })]));')
    assert json.loads(out) == [794, 1123, 1123, 794]


# --- 4. Paper size and orientation ------------------------------------------------------------------------


def test_a_boards_paper_and_orientation_are_kept_and_the_defaults_are_not(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    out = ai_client.put(url, json={"background": {"paper": "a3", "orientation": "landscape"}})
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"paper": "a3", "orientation": "landscape"}
    custom = ai_client.put(url, json={"background": {"paper": "custom", "paper_w": 200, "paper_h": 120}})
    assert custom.json()["background"] == {"paper": "custom", "paper_w": 200, "paper_h": 120, "orientation": "landscape"}
    back = ai_client.put(url, json={"background": {"paper": "a4", "orientation": "portrait", "paper_w": None, "paper_h": None}})
    assert back.json()["background"] == {}


def test_a_custom_size_is_dropped_when_the_paper_is_not_custom(ai_client):
    """Review 5883430964: a stored paper_w and paper_h stayed behind a named paper, and came back unasked."""
    url = f"/whiteboard/boards/{_board(ai_client)['id']}"
    ai_client.put(url, json={"background": {"paper": "custom", "paper_w": 200, "paper_h": 120}})
    named = ai_client.put(url, json={"background": {"paper": "letter"}})
    assert named.json()["background"] == {"paper": "letter"}
    stray = ai_client.put(url, json={"background": {"paper_w": 150}})
    assert stray.json()["background"] == {"paper": "letter"}


def test_a_paper_that_is_not_in_the_table_or_a_custom_size_out_of_range_is_refused(ai_client):
    board = _board(ai_client)
    for patch in ({"paper": "tabloid"}, {"orientation": "sideways"}, {"paper_w": 10}, {"paper_h": 9000}):
        refused = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": patch})
        assert refused.status_code == 422, patch


def test_the_page_table_holds_every_size_and_a_custom_one_in_millimetres():
    out = _node(
        _pdf_source()
        + ' const px = (bg) => wbPdf.pagePx(bg);'
        + ' console.log(JSON.stringify([px({ paper: "a3" }), px({ paper: "letter" }), px({ paper: "legal", orientation: "landscape" }),'
        + ' px({ paper: "custom", paper_w: 100, paper_h: 200 })]));'
    )
    # 96 px to the inch: A3 297 x 420 mm, Letter 8.5 x 11 in, Legal 8.5 x 14 in landscape, custom 100 x 200 mm.
    assert json.loads(out) == [[1123, 1587], [816, 1056], [1344, 816], [378, 756]]


def test_the_pdf_export_starts_from_the_boards_paper_and_orientation():
    out = _node(
        _pdf_source()
        + ' const bounds = { x: 0, y: 0, w: 400, h: 300 };'
        + ' const a = wbPdf.plan({ bounds, ...wbPdf.boardChoice({ paper: "a3", orientation: "landscape" }, { size: "a4", orientation: "auto", layout: "fit" }) });'
        + ' const b = wbPdf.plan({ bounds, ...wbPdf.boardChoice({}, { size: "letter", orientation: "auto", layout: "fit" }) });'
        + ' console.log(JSON.stringify([a[0].page, b[0].page]));'
    )
    a3, letter = json.loads(out)
    assert [round(v) for v in a3] == [1191, 842]  # A3 landscape: the board's choice beats the saved one
    assert letter == [792, 612]  # a board with no paper keeps the last choice made in the dialog (Auto: wide board, landscape)
    js = app_js_text()
    assert "wbPdf.boardChoice(wbBoardBackground(), wbPdf.savedChoice())" in js
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for ident in ("wb-bo-paper", "wb-bo-orient", "wb-bo-paper-w", "wb-bo-paper-h"):
        assert f'id="{ident}"' in html


# --- 5 and 6. PNG resolution and embedded board, one-file HTML export -------------------------------------------

EXPORT_MORE = ROOT / "frontend" / "js" / "whiteboard-export-more.js"


def _tiny_png() -> bytes:
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")


def _png_chunks(blob: bytes) -> list[tuple[bytes, bytes]]:
    import struct
    import zlib

    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    at, out = 8, []
    while at < len(blob):
        (length,) = struct.unpack(">I", blob[at : at + 4])
        kind, data = blob[at + 4 : at + 8], blob[at + 8 : at + 8 + length]
        (crc,) = struct.unpack(">I", blob[at + 8 + length : at + 12 + length])
        assert crc == zlib.crc32(kind + data), kind  # every chunk written keeps a correct CRC
        out.append((kind, data))
        at += 12 + length
    return out


def _run_export_more(png: bytes, options: str) -> dict:
    script = (
        "const wbFmtState = {};\n" + EXPORT_MORE.read_text(encoding="utf-8") + "\n"
        f"const input = Uint8Array.from(Buffer.from('{png.hex()}', 'hex'));\n"
        f"const out = wbFmtState.exporters.pngWith(input, {options});\n"
        "console.log(JSON.stringify({ hex: Buffer.from(out).toString('hex'), dpi: wbFmtState.exporters.dpiOf(out), rows: wbFmtState.exporters.rowsOf(out) }));"
    )
    return json.loads(_node(script))


@pytest.mark.parametrize("dpi,per_metre", [(72, 2835), (96, 3780), (150, 5906), (300, 11811)])
def test_a_png_export_writes_its_resolution_as_a_phys_chunk(dpi, per_metre):
    import struct

    out = _run_export_more(_tiny_png(), f"{{ dpi: {dpi} }}")
    chunks = _png_chunks(bytes.fromhex(out["hex"]))
    assert [kind for kind, _ in chunks] == [b"IHDR", b"pHYs", b"IDAT", b"IEND"]
    x, y, unit = struct.unpack(">IIB", chunks[1][1])
    assert (x, y, unit) == (per_metre, per_metre, 1)
    assert out["dpi"] == dpi


def test_a_png_can_carry_the_board_and_gives_it_back_with_every_character_kept():
    rows = [{"kind": "object", "id": 1, "link": False, "payload": {"kind": "shape", "data": {"text": "café → 日本"}}}]
    out = _run_export_more(_tiny_png(), f"{{ dpi: 96, rows: {json.dumps(rows)} }}")
    chunks = _png_chunks(bytes.fromhex(out["hex"]))
    assert [kind for kind, _ in chunks] == [b"IHDR", b"pHYs", b"tEXt", b"IDAT", b"IEND"]
    keyword, _, body = chunks[2][1].partition(b"\0")
    assert keyword == b"tessellate-board" and body.isascii()  # a tEXt chunk is Latin-1: the JSON is plain ASCII
    assert out["rows"] == rows
    # No resolution and no board: the file is returned as it was.
    assert _run_export_more(_tiny_png(), "{}")["hex"] == _tiny_png().hex()


def test_the_png_export_dialog_offers_a_border_a_resolution_and_a_copy_of_the_board():
    js = app_js_text()
    for needle in (
        "wbFmtState.exporters.pngWith(",
        "exporters.dpis",
        "wb-export-border",
        "wb-export-embed",
        "wbFmtState.exporters.rowsOf(",
        "pad = 0",
    ):
        assert needle in js, needle
    assert "/js/whiteboard-export-more.js" in (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")


def test_the_html_export_is_one_file_that_needs_nothing_from_the_network():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100"><rect x="0" y="0" width="200" height="100" fill="#fff"/></svg>'
    script = (
        "const wbFmtState = {};\n" + EXPORT_MORE.read_text(encoding="utf-8")
        + f"\nconsole.log(JSON.stringify(wbFmtState.exporters.htmlPage({json.dumps(svg)}, 'Plan <1> & \"two\"')));"
    )
    page = json.loads(_node(script))
    assert page.startswith("<!DOCTYPE html>") and "<title>Plan &lt;1&gt; &amp; &quot;two&quot;</title>" in page
    assert 'viewBox="0 0 200 100"' in page and '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">' in page  # it fills the window; the viewBox is the size
    lowered = page.lower()
    # Offline and CSP-safe: no address anywhere, no external script, link or font, no inline style attribute or handler.
    for banned in ("<link", " src=", "@import", "url(", " style=", " onclick=", "eval(", "fetch(", "xmlhttprequest"):
        assert banned not in lowered, banned
    assert lowered.count("<script") == 1 and lowered.count("<style") == 1
    assert "https://" not in lowered and lowered.count("http://") == 1  # only the SVG namespace, which is a name and not an address
    js = app_js_text()
    assert "wbFmtState.exporters.htmlPage(" in js and 'value: "html"' in js


# --- 7. Rulers and units ----------------------------------------------------------------------------------

OPTIONS = ROOT / "frontend" / "js" / "whiteboard-options.js"


def _opts(expression: str):
    """Run an expression against the options file's exports, with the page's names stubbed."""
    script = "const wbFmtState = {}; const onSurface = () => {};\n" + OPTIONS.read_text(encoding="utf-8") + f"\nconsole.log(JSON.stringify({expression}));"
    return json.loads(_node(script))


def test_a_boards_units_are_kept_and_px_the_default_is_not(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    out = ai_client.put(url, json={"background": {"units": "mm"}})
    assert out.status_code == 200, out.text
    assert out.json()["background"] == {"units": "mm"}
    assert ai_client.put(url, json={"background": {"units": "px"}}).json()["background"] == {}
    refused = ai_client.put(url, json={"background": {"units": "furlong"}})
    assert refused.status_code == 422


def test_a_length_converts_between_board_pixels_and_the_boards_unit_at_96_to_the_inch():
    # 96 px is an inch, 25.4 mm, 2.54 cm and 72 pt; the display rounds to what the unit can say.
    shown = _opts('["px", "mm", "cm", "in", "pt"].map((u) => wbFmtState.opts.show(96, u))')
    assert shown == ["96", "25.4", "2.54", "1", "72"]
    back = _opts('["px", "mm", "cm", "in", "pt"].map((u) => wbFmtState.opts.read(String(wbFmtState.opts.show(96, u)), u))')
    assert back == [96, 96, 96, 96, 96]
    assert _opts('wbFmtState.opts.read("not a number", "mm")') is None


def test_ruler_ticks_follow_the_zoom_and_the_unit():
    # At 1x in px a major tick is wide enough for its label (50 or more screen px apart) and sits on a round number.
    one = _opts("wbFmtState.opts.ticks(0, 400, 1, 'px')")
    majors = [t["v"] for t in one if t["major"]]
    assert majors == [0, 100, 200, 300, 400]
    assert all(t["at"] == t["v"] for t in one if t["major"])  # px: the value is the board position
    # Zoomed in 4x the same board span needs finer steps, and a tick's screen gap never drops under the label width.
    zoomed = _opts("wbFmtState.opts.ticks(0, 100, 4, 'px')")
    zmajors = [t["v"] for t in zoomed if t["major"]]
    assert zmajors == [0, 20, 40, 60, 80, 100]
    assert min(b - a for a, b in zip(zmajors, zmajors[1:])) * 4 >= 50
    # Millimetres: the ticks are millimetres on a round step, positioned in board pixels (96 / 25.4 each).
    mm = _opts("wbFmtState.opts.ticks(0, 200, 1, 'mm')")
    mm_major = [t for t in mm if t["major"]]
    assert [t["v"] for t in mm_major][:3] == [0, 20, 40] or [t["v"] for t in mm_major][:3] == [0, 10, 20]
    step = mm_major[1]["v"] - mm_major[0]["v"]
    assert abs((mm_major[1]["at"] - mm_major[0]["at"]) - step * 96 / 25.4) < 1e-6
    # Visible range in negative board space still ticks from the first round number inside it.
    negative = _opts("wbFmtState.opts.ticks(-250, 50, 1, 'px')")
    assert [t["v"] for t in negative if t["major"]][0] == -200


def test_the_rulers_are_a_view_switch_drawn_on_every_view_change_and_the_fields_show_the_unit():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for ident in ("wb-view-rulers", "wb-bo-units"):
        assert f'id="{ident}"' in html
    js = app_js_text()
    assert "wbFmtState.opts?.drawRulers(t);" in js  # the zoom and pan callback redraws them
    fmt = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    assert "wbFmtState.opts?.show(" in fmt and "wbFmtState.opts?.read(" in fmt
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".wb-ruler" in css


def test_the_grid_size_says_it_is_always_in_pixels():
    """Review 5883430964, point 4: the grid is stored as whole pixels (4 to 200) so its lines and snapping land on whole
    pixels; following the Units option would round every value through mm or inches. So it says pixels instead."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    row = html[html.index('id="wb-bo-grid-size"') - 120 : html.index('id="wb-bo-grid-size"') + 400]
    assert "Grid size (px)" in row and "always in pixels whatever the units" in row
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Grid size (4 to 200 pixels whatever the units" in guide
