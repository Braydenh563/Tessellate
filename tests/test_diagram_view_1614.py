"""INBOX 1614 (DOCUMENTS_PLAN 22.4 R2): the picture shares the blocks pane's height, and it zooms, pans and fits.

The heights themselves are measured in a browser (docs/roadmap/agent-remaining/diagram-r2-1104.md names the
sweep and the numbers); this file holds what a diff can break: the cascade that left the picture 19px short,
the narrow rule that keeps its own 26vh, and the zoom maths (run under node where it is installed).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
MERMAID_CSS = (ROOT / "frontend" / "css" / "mermaid-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_the_picture_margin_is_not_beaten_by_the_mermaid_figure_rule():
    # `.md-mermaid` (a later file) gives every figure a block margin; the picture's own `margin: 0` must out-rank it.
    assert "margin: var(--space-4) 0;" in _rule(MERMAID_CSS, ".md-mermaid")
    assert "margin: 0;" in _rule(CSS, ".dgm .dgm-picture")
    assert not re.search(r"^\.dgm-picture \{", CSS, re.M)


def test_the_two_panes_stretch_together_in_a_wide_container_and_the_picture_keeps_38dvh_below_600():
    body = _rule(CSS, ".dgm-body")
    assert "display: grid;" in body and "align-items" not in body
    assert "38dvh" not in CSS[: CSS.index("@container (max-width: 599.98px)")]
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    # R6.1: 26vh drew a three-block flowchart at 48% with 6 px text, and the zoom bar covered its lower node.
    assert "block-size: 38dvh;" in narrow


VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-view.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.view.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_fit_keeps_an_8px_margin_never_enlarges_and_the_range_is_a_quarter_to_five_times_fit():
    # A tall drawing in a wide pane is fitted by height: 400 drawn units into 300px leave 8px above and below.
    assert _math("m.fitScale(200, 400, 800, 300)") == pytest.approx(284 / 400)
    # A drawing smaller than the pane stays at its drawn size.
    assert _math("m.fitScale(100, 50, 800, 600)") == 1
    # The range is relative to Fit, not to the drawn size.
    assert _math("[m.clamp(0.001, 0.4), m.clamp(99, 0.4)]") == [pytest.approx(0.1), pytest.approx(2.0)]
    assert _math("[m.MIN, m.MAX, m.MARGIN]") == [0.25, 5, 8]


@needs_node
def test_a_wheel_notch_is_one_step_and_a_trackpad_delta_is_smaller_and_the_size_comes_from_the_viewbox():
    assert _math("[m.wheel(-100), m.wheel(100)]") == [pytest.approx(1.25), pytest.approx(0.8)]
    assert 1 < _math("m.wheel(-4)") < 1.01
    assert _math("m.wheel(-9999)") == pytest.approx(1.25)
    assert _math('m.size(\'<svg viewBox="0 0 360 1006.5" width="100%">\')') == {"w": 360, "h": 1006.5}
    assert _math("m.size('<svg></svg>')") is None


def test_the_view_is_one_lazy_file_with_one_export_a_zoom_bar_on_the_dock_recipe_and_a_listener_list():
    #: The view is still the one lazy script; its value field (styles and script, the zoom percentage) rides with it (INBOX 1694).
    assert 'diagramView: ["/css/value-field.css", "/js/value-field.js", "/js/diagram-view.js"]' in MERMAID_JS
    assert VIEW.startswith("//") and "\n(() => {" in VIEW and VIEW.rstrip().endswith("})();")
    assert VIEW.count("diagramModel.view = ") == 1 and "window." not in VIEW
    assert 'ensureModule("diagramView")' in BUILDER and "diagramModel.view.wire(S)" in BUILDER
    assert "onpaint?." not in BUILDER and "(fig.onpaint ||= []).push(paint)" in VIEW
    # Ctrl+wheel and pinch about the pointer, + - 0 and the arrows, and the four buttons in a plain .dock.
    for needle in ("event.ctrlKey", "{ passive: false }", 'ArrowLeft:', 'event.key === "0"', 'bar.className = "dock dgm-zoom"', '"Zoom in"', '"Zoom out"', '"Fit"', 'label: "Zoom percent"'):
        assert needle in VIEW, needle
    # The zoom is a width on the image plus the figure's scroll (the technique of the old `zoomable`). 1679 l: a transform is
    # allowed only as the next frame's stand-in while an input is in motion; `drop` clears it before the width is committed.
    assert "img.style.width" in VIEW and VIEW.count("style.transform =") == 2 and 'style.transform = d.img.style.transformOrigin' in VIEW
    # Zoom is kept across a redraw as a scale and reset only when the diagram's kind word changes.
    assert "state.kind && kind !== state.kind" in VIEW


def test_the_zoom_bar_is_a_corner_dock_hidden_until_there_is_a_picture():
    bar = _rule(CSS, ".dgm-zoom")
    assert "position: absolute;" in bar and "background: var(--modal-bg);" in bar
    assert ".dgm-stage:not(.dgm-zoomable) .dgm-zoom {\n  display: none;" in CSS
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert ".dgm-stage > .dgm-picture {\n    block-size: auto;" in narrow


def test_the_corner_readout_names_the_true_zoom_after_every_path_1652():
    # 100% is the drawing's own size; the last button is the live readout, repainted by every zoom path (they all end in paint).
    assert _math("m.percent(1)") == 100 and _math("m.percent(1.25)") == 125 and _math("m.percent(0.333)") == 33
    # 1679 l: the readout is one helper (`readout`), called by paint and by a gesture's frame, so it names the zoom aimed at too.
    assert "level?.set(math.percent(scale))" in VIEW
    assert VIEW.index("buttons.out.disabled = math.atEnd(scale") < VIEW.index("level?.set(math.percent(scale))")


@needs_node
def test_fit_never_shrinks_the_text_below_eleven_pixels_and_the_figure_scrolls_past_it():
    # 1679 slice 7: a 220 by 1300 drawing in a 755 by 482 stage fitted to 0.35 (5.6 px text); the floor is 0.69 (16 px x 0.69 = 11 px).
    assert _math("m.FLOOR") == pytest.approx(0.69)
    assert _math("m.fitScale(220, 1300, 755, 482)") == pytest.approx(0.69)
    # A drawing that fits above the floor is fitted as before, and a small one still stays at its drawn size.
    assert _math("m.fitScale(200, 400, 800, 300)") == pytest.approx(284 / 400)
    assert _math("m.fitScale(100, 50, 800, 600)") == 1


@needs_node
def test_a_tall_drawing_in_a_wide_stage_offers_to_turn_sideways_once_and_not_for_a_sideways_one():
    offer = "m.sideways"
    assert _math(f"{offer}({{w: 220, h: 464}}, {{width: 755, height: 482}}, 'TD')") is True
    assert _math(f"{offer}({{w: 220, h: 464}}, {{width: 755, height: 482}}, 'LR')") is False
    assert _math(f"{offer}({{w: 220, h: 300}}, {{width: 755, height: 482}}, 'TD')") is False
    assert _math(f"{offer}({{w: 220, h: 464}}, {{width: 300, height: 600}}, 'TD')") is False
    assert _math(f"{offer}({{w: 220, h: 464}}, {{width: 755, height: 482}}, 'BT')") is True


def test_the_offer_is_one_line_under_the_toolbar_with_two_buttons_and_one_commit():
    view = (JS / "diagram-outline.js").read_text(encoding="utf-8")
    assert "dgm-sideways" in view and "Turn it sideways" in view and 'S.turn("LR")' in view
    assert "diagramModel.outline?.offer(S, f < 1 && math.sideways(" in (JS / "diagram-view.js").read_text(encoding="utf-8")
    assert "dgm-sideways" in (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_a_drag_pan_reads_no_layout_in_its_move_handler_and_writes_the_scroll_once_a_frame():
    """L-documents-89: the pan's `pointermove` summed its moves and wrote `scrollLeft` once a frame; it read `scrollWidth`
    (a forced layout) and shut the menus on every move before."""
    text = (JS / "diagram-view.js").read_text(encoding="utf-8")
    start = text.index('fig.addEventListener("pointermove"')
    handler = text[start : text.index("const lift = ", start)]
    for forbidden in ("roomy()", "scrollLeft", "scrollTop", "scrollWidth", "clientWidth", "getBoundingClientRect"):
        assert forbidden not in handler, forbidden
    assert "nextFrame(pay)" in handler and "!held" in handler and "!shut" in handler
    assert "room = roomy();" in text and "      pay();\n      start = null;" in text

