"""Quick sketch, rebuilt as a paint pad of its own (INBOX 1352; the owner
2026-10-26: "prioritise the quick sketch improvements, redesign and extension
... I want to copy it to a separate repo").

The pad is `frontend/js/sketch-pad.js` and `frontend/css/sketch-pad.css`,
loaded on the first `openSketch` (media.js). It builds its own markup and
reaches the app only through the host object media.js hands it, so the same
two files run on `tools/sketch-standalone/`. The geometry is checked
here by running the pad's own helpers under node; the tools end to end are
`scratchpad/ui-sweeps/paint1026-pad.js` (34 checks at 1440, 720 and 390, in
the app and on the standalone page).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAD = ROOT / "frontend" / "js" / "sketch-pad.js"
PAD_CSS = ROOT / "frontend" / "css" / "sketch-pad.css"
MEDIA = ROOT / "frontend" / "js" / "media.js"
STANDALONE = ROOT / "tools" / "sketch-standalone"


def _code(text: str) -> str:
    """The file without its comments, so a comment naming a global is not a use."""
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _geometry(expr: str):
    """Evaluate `expr` against `SketchPad._geometry` (as `g`) under node."""
    script = (
        "global.window = { addEventListener() {} };"
        "global.document = { addEventListener() {} };"
        f"require({json.dumps(str(PAD))});"
        "const g = window.SketchPad._geometry;"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


# --- shapes: corner to corner, Alt from the centre, Shift square -------------------


@needs_node
def test_a_box_runs_from_the_press_to_the_pointer():
    assert _geometry("g.spBox(100, 100, 220, 160)") == {"x": 100, "y": 100, "w": 120, "h": 60}


@needs_node
def test_a_box_dragged_up_and_left_still_ends_at_the_pointer():
    assert _geometry("g.spBox(100, 100, 40, 70)") == {"x": 40, "y": 70, "w": 60, "h": 30}


@needs_node
def test_shift_makes_a_square_that_grows_towards_the_pointer():
    """The square takes the longer side and keeps the drag's direction, so a
    drag up and left is a square up and left of the press (PaintZ's rule)."""
    assert _geometry("g.spBox(100, 100, 40, 80, { shift: true })") == {"x": 40, "y": 40, "w": 60, "h": 60}


@needs_node
def test_alt_puts_the_press_at_the_centre():
    assert _geometry("g.spBox(100, 100, 160, 130, { alt: true })") == {"x": 40, "y": 70, "w": 120, "h": 60}


@needs_node
def test_shift_snaps_a_line_to_the_nearest_45_degrees():
    flat = _geometry("g.spLineEnds(0, 0, 100, 12, { shift: true })")
    assert flat["y2"] == 0 and flat["x2"] == pytest.approx(100.717, abs=0.01)
    diagonal = _geometry("g.spSnap45(0, 0, 100, 90)")
    assert diagonal["x"] == pytest.approx(diagonal["y"])


@needs_node
def test_alt_mirrors_a_line_through_the_press():
    assert _geometry("g.spLineEnds(50, 50, 80, 60, { alt: true })") == {"x1": 20, "y1": 40, "x2": 80, "y2": 60}


# --- the bucket ---------------------------------------------------------------------


@needs_node
def test_the_fill_stays_inside_a_closed_outline_and_tucks_under_its_edge():
    """A 10x10 sheet with a closed 1px square from (2,2) to (7,7): a fill from
    the middle covers the 4x4 inside, grows one pixel under the outline, and
    never reaches the corner outside it."""
    expr = (
        "(() => { const w = 10, h = 10, d = new Uint8ClampedArray(w * h * 4);"
        " for (let y = 2; y <= 7; y++) for (let x = 2; x <= 7; x++)"
        "  if (x === 2 || x === 7 || y === 2 || y === 7) d[(y * w + x) * 4 + 3] = 255;"
        " const m = g.spFloodMask(d, w, h, 5, 5);"
        " return { inside: m[5 * w + 5], edge: m[2 * w + 5], corner: m[0], count: m.reduce((a, b) => a + b, 0) }; })()"
    )
    got = _geometry(expr)
    assert got["inside"] == 1 and got["edge"] == 1 and got["corner"] == 0
    assert got["count"] == 16 + 16  # the 4x4 inside plus the ring of 16 it grows into


# --- self-contained -----------------------------------------------------------------


def test_the_pad_reads_no_app_global():
    """Everything from the app comes through the host: no `$(`, no fetch, no
    app function called by name. This is what lets the two files be copied."""
    code = _code(PAD.read_text(encoding="utf-8"))
    for name in ("$(", "fetch(", "api(", "toast(", "confirmDialog", "kebabMenu", "wireHelpPopover", "prefs.json", "loadEntries", "HIGHLIGHTER_STYLE"):
        assert name not in code, name
    assert code.lstrip().startswith("(() => {") and code.rstrip().endswith("})();")


def test_the_host_has_a_fallback_for_every_hook():
    pad = PAD.read_text(encoding="utf-8")
    defaults = pad[pad.index("const SKETCH_HOST_DEFAULTS") : pad.index("};", pad.index("const SKETCH_HOST_DEFAULTS"))]
    media = MEDIA.read_text(encoding="utf-8")
    host = media[media.index("function sketchHost()") :]
    host = host[: host.index("\n}")]
    for hook in ("save", "toast", "confirm", "prefs", "highlighter", "menu", "wireHelp", "singleKeys", "close"):
        assert f"{hook}:" in defaults, hook
        assert f"{hook}:" in host, hook


def test_the_app_loads_the_pad_lazily_and_keeps_no_markup_for_it():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<div class="card glass" id="sketch-card"></div>' in html
    assert "sketch-toolbar" not in html and "sketch-canvas" not in html
    assert '<script src="/js/sketch-pad.js"' not in html
    media = MEDIA.read_text(encoding="utf-8")
    assert '"/js/sketch-pad.js"' in media and '"/css/sketch-pad.css"' in media


def test_every_tool_has_a_key_and_says_it():
    pad = PAD.read_text(encoding="utf-8")
    tools = re.findall(r'\{ id: "(\w+)", key: "([A-Z])", label: "([^"]+)"', pad)
    assert len(tools) == 13
    assert len({key for _, key, _ in tools}) == 13
    assert "`${label} (${key})`" in pad and "tip: tool.tip" in pad


def test_the_standalone_page_uses_the_same_files():
    page = (STANDALONE / "index.html").read_text(encoding="utf-8")
    for path in ("../../frontend/css/00-tokens-shell.css", "../../frontend/css/sketch-pad.css", "../../frontend/js/sketch-pad.js", "../../frontend/vendor/phosphor/style.css"):
        assert path in page, path
    assert "<script>" not in page, "the page's own script is boot.js (the app's CSP has no inline scripts either)"
    readme = (STANDALONE / "README.md").read_text(encoding="utf-8")
    for name in ("sketch-pad.js", "sketch-pad.css", "00-tokens-shell.css", "standalone.css", "boot.js", "phosphor"):
        assert name in readme, name


# --- the look: the app's recipes ----------------------------------------------------


def test_the_bar_is_a_borderless_tint_and_a_dock():
    css = PAD_CSS.read_text(encoding="utf-8")
    bar = re.search(r"(?m)^\.sp-bar \{([^}]*)\}", css).group(1)
    assert "background: var(--field-inset);" in bar and "border:" not in bar
    assert '"data-dock-name": "sketch"' in PAD.read_text(encoding="utf-8")


def test_every_swatch_is_ringed_so_white_shows_on_white():
    css = PAD_CSS.read_text(encoding="utf-8")
    swatch = re.search(r"(?m)^\.sp-swatch \{([^}]*)\}", css).group(1)
    assert "box-shadow: inset 0 0 0 1px var(--control-edge);" in swatch


def test_a_stroke_never_raises_the_text_kebab():
    """INBOX 1303: a press on the pad is not a text selection."""
    pad = PAD.read_text(encoding="utf-8")
    down = re.search(r"function onDown\(e\) \{[\s\S]*?\n  \}", pad).group(0)
    assert "e.preventDefault()" in down
