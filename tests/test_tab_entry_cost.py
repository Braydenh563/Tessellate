"""Tab entry cost (perf sweep 2026-10-17, scratchpad/ui-sweeps/tabenter.js).

The frame spikes on a tab press were measured with the companion off at 4x
CPU, on a 2,000-note notebook, and traced by Chromium event
(scratchpad/ui-sweeps/tabtrace.js). Each test here holds one win that a
source-level check can hold; the numbers are in the commit that added it.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start : source.index("\n}\n", start)]


def test_a_hidden_graph_tab_draws_nothing():
    """Leaving the Graph tab left the canvas drawing for about a second (37
    draws, 60 ms at 1x, 240 ms at 4x) into the next tab's entry window: the
    worker's last ticks still arrived and each asked for a frame of a map
    nobody could see. A draw for the tab's own map is dropped while the page
    is hidden; the next visit renders the map in full (`switchTab`)."""
    hidden = _body(CANVAS, "function gcTabHidden(")
    assert 'tab-graph' in hidden and 'classList.contains("hidden")' in hidden
    request = _body(CANVAS, "function gcRequestDraw(")
    assert request.index("gcTabHidden(s)") < request.index("requestAnimationFrame")
    draw = _body(CANVAS, "function gcDraw(")
    assert re.search(r"if \(gcTabHidden\(s\)\)", draw[:400])


EDITOR = (JS / "editor.js").read_text(encoding="utf-8")


def test_focusing_a_composer_does_not_fetch_the_library_bundle_at_once():
    """Arriving on Chat focuses the composer (`switchTab`), and the warm-up on
    focus used to fetch and run the Library bundle (d3, documents.js, the
    whiteboard files: 17 scripts, ~2 MB) in that same press: the first long
    task of every first Chat visit. It now waits out the arrival and runs when
    the page is idle, and a keystroke that needs the adapter still asks for
    the bundle itself (`editorSurfaceFor`), so the first "/" is not lost."""
    listener = EDITOR[EDITOR.index("if (typeof asSurface === \"function\") return;\n    editorWarmSurfaceModule") :]
    listener = listener[: listener.index("\n);\n")]
    assert "editorWarmSurfaceModule(el)" in listener
    assert "editorEnsureSurfaceModule" not in listener
    warm = _body(EDITOR, "function editorWarmSurfaceModule(")
    assert re.search(r"setTimeout\([^;]*,\s*(\d{4,})\s*\)", warm) or "EDITOR_WARM_DELAY_MS" in warm
    assert "requestIdleCallback" in warm
    assert 'document.activeElement === el' in warm
    assert re.search(r"EDITOR_WARM_DELAY_MS = (\d+)", EDITOR) and int(re.search(r"EDITOR_WARM_DELAY_MS = (\d+)", EDITOR).group(1)) >= 1500
    # The keystroke path is untouched.
    assert "editorEnsureSurfaceModule(box);" in _body(EDITOR, "function editorSurfaceFor(")


def test_a_caret_does_not_resolve_the_surface_adapter():
    """`selectionchange` fires as a composer takes focus; the selection bar
    resolved the surface first, which fetched the Library bundle, to learn
    there was no selection. A collapsed caret in a plain box is answered
    before the adapter is asked for."""
    sync = _body(EDITOR, "function selectionBarSync(")
    assert sync.index("raw.selectionStart === raw.selectionEnd") < sync.index("editorSurfaceFor(")
    assert 'typeof asSurface !== "function"' in sync[: sync.index("editorSurfaceFor(")]


DASH = (JS / "dashboard.js").read_text(encoding="utf-8")


def test_the_dashboard_sky_does_not_parse_a_p5_colour_per_shape():
    """Idle on the Dashboard at 4x CPU the constellation was 527 ms of the 540
    ms the page was busy in 5 s, 426 ms of it p5's colour parser (`value`):
    one `fill` per wash strip (55), one `stroke` per connecting line and two
    `fill`s per star, every frame. The scene draws on the canvas context with
    one gradient for the wash and a colour string per shape, and reads the
    accent's hue once."""
    start = DASH.index("    const scene = (t, settled = false) => {")
    scene = DASH[start : DASH.index("\n    };\n", start)]
    for call in ("p.fill(", "p.stroke(", "p.rect(", "p.circle(", "p.line(", "p.color("):
        assert call not in scene, call
    assert "createLinearGradient" in scene
    assert "washHue" in DASH[start - 600 : start] or "washHue ??=" in scene
