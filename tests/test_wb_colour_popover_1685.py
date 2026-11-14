"""INBOX 1685 (the owner, 2026-11-05): "I unticked filled and it switched to
blue ... that popup tool bar needs some ui fixing ... I cant find where to
change the transparency in the colours and can it be easier to enter custom
rgb or hex codes".

Three classes, each tested where it lives:
- Filled, every toggle: turning a fill off keeps the shape's own colour, so the
  swatch never falls back to the default and Filled on brings the colour back.
- The colour parser behind the hex and R, G, B fields: what a paste may be.
- The one app colour popover: its fields exist, in the one popover every board
  colour field opens, and the native dialog is gone from it.
The browser half (gaps, hit sizes, contrast) is the sweep named in the plan."""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
BOARD = frontend_text("whiteboard.js")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(name: str) -> str:
    """A function of the file, or of the colour kit it sits inside (indented)."""
    m = re.search(rf"^( *)(?:async )?function {name}\(", FORMAT, re.M)
    assert m, name
    return FORMAT[m.start() : FORMAT.index(f"\n{m.group(1)}}}\n", m.start()) + 2 + len(m.group(1))]


def _kit() -> str:
    start = FORMAT.index("const wbColour = (() => {")
    return FORMAT[start : FORMAT.index("\n})();\n", start) + 8]


def _run(names: list[str], body: str):
    del names  # the kit holds them all; kept so each test says what it exercises
    code = "function wbHexOf() { return null; }\n" + _kit() + f"\nprocess.stdout.write(JSON.stringify({body}));"
    proc = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout)


@needs_node
def test_filled_off_keeps_a_shapes_colour_and_on_brings_it_back() -> None:
    names = ["wbFillIsOn", "wbFillTogglePatch"]
    sketch = {"fill": "#22aa66", "fillOpacity": 0.6, "gradient": {"to": "#fff", "dir": "s"}}
    off = _run(names, f"wbColour.fillToggle('sketch', {json.dumps(sketch)}, false, '#3355ff')")
    assert off == {"fillOpacity": 0}, off
    kept = {**sketch, **off}
    assert _run(names, f"wbColour.fillIsOn('sketch', {json.dumps(kept)})") is False
    on = _run(names, f"wbColour.fillToggle('sketch', {json.dumps(kept)}, true, '#3355ff')")
    assert on["fill"] == "#22aa66" and on["fillOpacity"] == 1, on
    # A shape that never had a fill takes the tool's colour on, and off is a no-op.
    assert _run(names, "wbColour.fillToggle('sketch', {}, true, '#3355ff')") == {"fill": "#3355ff", "fillOpacity": 1}
    assert _run(names, "wbColour.fillToggle('sketch', {}, false, '#3355ff')") == {}


@needs_node
def test_filled_off_on_a_text_box_keeps_its_bg() -> None:
    names = ["wbFillIsOn", "wbFillTogglePatch"]
    box = {"bg": "#ffcc00"}
    off = _run(names, f"wbColour.fillToggle('object', {json.dumps(box)}, false, '#3355ff')")
    assert off == {"bg_alpha": 0}, off
    kept = {**box, **off}
    assert _run(names, f"wbColour.fillIsOn('object', {json.dumps(kept)})") is False
    on = _run(names, f"wbColour.fillToggle('object', {json.dumps(kept)}, true, '#3355ff')")
    # bg_alpha is `undefined` (JSON drops it): the apply step deletes the key, so the fill is solid again.
    assert on == {"bg": "#ffcc00"}, on
    # Old data: a transparent bg is unfilled, and Filled on gives it a colour.
    assert _run(names, "wbColour.fillIsOn('object', {bg: 'transparent'})") is False
    assert _run(names, "wbColour.fillToggle('object', {bg: 'transparent'}, true, '#3355ff')")["bg"] == "#3355ff"
    # A diagram keeps its accent: only the alpha moves.
    assert _run(names, "wbColour.fillToggle('diagram', {}, false, '#3355ff')") == {"bg_alpha": 0}
    assert _run(names, "wbColour.fillIsOn('diagram', {bg_alpha: 0})") is False


@needs_node
def test_a_new_fill_colour_keeps_the_fill_opacity_and_brings_back_a_hidden_one() -> None:
    names: list[str] = []
    assert _run(names, "wbColour.fillColour('sketch', {fill: '#111111', fillOpacity: 0.5}, '#ff0000')") == {"fill": "#ff0000", "fillOpacity": 0.5}
    assert _run(names, "wbColour.fillColour('sketch', {fill: '#111111', fillOpacity: 0}, '#ff0000')") == {"fill": "#ff0000", "fillOpacity": 1}
    assert _run(names, "wbColour.fillColour('object', {bg: '#111111', bg_alpha: 0.3}, '#ff0000')") == {"bg": "#ff0000", "bg_alpha": 0.3}
    assert _run(names, "wbColour.fillColour('object', {bg: '#111111', bg_alpha: 0}, '#ff0000')") == {"bg": "#ff0000"}


def test_every_filled_toggle_uses_the_one_patch() -> None:
    assert "wbColour.fillToggle(" in _function_body_of(FORMAT, 'on("wb-fmt-fill-on"')
    bar = BOARD[BOARD.index('getElementById("wb-prop-shapefill-on")?.addEventListener') :][:900]
    assert "wbFillTogglePatch" in bar or "wbFmtApply" in bar
    assert 'fill: e.target.checked ? document.getElementById("wb-prop-shapefill").value : undefined' not in BOARD
    assert 'case "fill-on": return wbColour.fillIsOn(' in FORMAT


def _function_body_of(source: str, marker: str) -> str:
    start = source.index(marker)
    return source[start : start + 800]


@needs_node
@pytest.mark.parametrize(
    ("text", "expect"),
    [
        ("#3af", {"hex": "#33aaff", "alpha": None}),
        ("#33aaff", {"hex": "#33aaff", "alpha": None}),
        ("33aaff", {"hex": "#33aaff", "alpha": None}),
        ("#33aaff80", {"hex": "#33aaff", "alpha": 0.5}),
        ("#3af8", {"hex": "#33aaff", "alpha": 0.53}),
        ("rgb(51, 170, 255)", {"hex": "#33aaff", "alpha": None}),
        ("rgb(51 170 255 / 25%)", {"hex": "#33aaff", "alpha": 0.25}),
        ("rgba(51,170,255,0.4)", {"hex": "#33aaff", "alpha": 0.4}),
        ("51, 170, 255", {"hex": "#33aaff", "alpha": None}),
        ("hsl(200, 100%, 60%)", {"hex": "#33bbff", "alpha": None}),
        ("hsla(0 100% 50% / 0.5)", {"hex": "#ff0000", "alpha": 0.5}),
        ("  #FFF  ", {"hex": "#ffffff", "alpha": None}),
        ("#12", None),
        ("rgb(300, 0, 0)", {"hex": "#ff0000", "alpha": None}),
        ("not a colour", None),
        ("", None),
    ],
)
def test_the_colour_parser_takes_what_people_paste(text: str, expect) -> None:
    got = _run(["wbColourParse"], f"wbColour.parse({json.dumps(text)})")
    assert got == expect, (text, got)


def test_the_popover_has_the_fields_and_no_native_dialog() -> None:
    menu = _function("wbOpenColourMenu")
    for needle in ("wbColour.fields(", "wbColour.opacity("):
        assert needle in menu, needle
    assert "showPicker" in menu  # only the no-module fallback at the top
    assert menu.count("showPicker") == 1
    assert "More colours" not in menu
    fields = _function("wbColourFields")
    for word in ('"Hex"', '"Red"', '"Green"', '"Blue"', "wbColourParse"):
        assert word in fields, word
    assert "EyeDropper" in menu or "EyeDropper" in fields


def test_every_colour_field_names_its_opacity_or_says_it_has_none() -> None:
    table = FORMAT[FORMAT.index("const WB_COLOUR_ALPHA") :][:1500]
    for field in ("wb-fmt-fill", "wb-prop-shapefill", "wb-prop-bg", "wb-fmt-stroke", "wb-prop-color", "wb-prop-border", "wb-fmt-ink"):
        assert f'"{field}"' in table, field
    assert "Opacity" in _function("wbColourOpacity")


def test_the_popover_styles_use_tokens_only() -> None:
    start = LAZY.index(".wb-colour-fields {")
    block = LAZY[start : LAZY.index(".wb-colour-opacity input[type=\"range\"]", start)]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
    assert not re.search(r"\b\d+px\b", block.replace("1px", "").replace("2px", ""))


def test_a_blank_number_box_is_ignored_never_read_as_zero() -> None:
    # Review of 1685: Number("") is 0, so a cleared Opacity hid the fill and a
    # cleared Red saved black. A blank or non-number box reverts instead.
    save = _function("wbColourOpacity")
    assert 'String(raw).trim() === ""' in save
    fields = _function("wbColourFields")
    assert "|| 0" not in fields
    assert "trim()" in fields


def test_no_menu_row_opens_the_native_colour_dialog() -> None:
    # Review of 1685: showPicker() skips the click the popover listens for.
    assert "showPicker" not in BOARD.replace("`showPicker()`", "")


def test_the_swatch_grid_fits_a_phone() -> None:
    assert re.search(r"\.wb-colour-menu \.swatch-picker \{[^}]*repeat\(auto-fill, var\(--target-min\)\)[^}]*100vw", LAZY)
