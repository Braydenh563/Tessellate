"""INBOX 1679 (l), slice 13: the picture pane's zoom and pan answer in the next frame.

Latency and evenness are measured in a browser (`scratchpad/ui-sweeps/diagram-escape.js pan-zoom`, numbers in
docs/roadmap/agent-remaining/diagram-1679-1104.md); this file holds what a diff can break: the pure maths (run under node)
and the shape of the code (a transform first, the real width after, one paint per frame).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-view.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.view.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_button_step_lands_on_a_rung_so_every_step_is_the_same_ratio():
    # From Fit: presses climb 1.25 each; from a wheel's odd scale the first press joins the ladder.
    ups = _math("(()=>{let s=0.8,o=[s];for(let i=0;i<9;i++){s=m.rung(s,0.8,1);o.push(s)}return o})()")
    ratios = [b / a for a, b in zip(ups, ups[1:])]
    assert all(abs(r - 1.25) < 1e-6 for r in ratios[:7]), ratios
    assert ups[-1] <= 5 * 0.8 + 1e-9
    odd = _math("m.rung(0.8*1.6,0.8,1)")
    assert abs(odd / 0.8 - 1.25**3) < 1e-6  # 1.6 sits between rung 2 and 3
    down = _math("m.rung(0.8*1.6,0.8,-1)")
    assert abs(down / 0.8 - 1.25**2) < 1e-6
    assert abs(_math("m.rung(0.8*1.25,0.8,-1)") - 0.8) < 1e-9


@needs_node
def test_the_ladder_stops_where_the_range_does_and_the_ends_are_reported():
    assert _math("m.rung(0.8*5,0.8,1)") == pytest.approx(4.0)
    assert _math("m.rung(0.8*0.25,0.8,-1)") == pytest.approx(0.8 * 0.25)
    ends = _math("[m.atEnd(0.8*5,0.8,1),m.atEnd(0.8*1.25**7,0.8,1),m.atEnd(0.8,0.8,1),m.atEnd(0.8*0.25,0.8,-1)]")
    # 1679 m: the top is the one range end the wheel also clamps to, so the rung below it (4.77 times Fit) is not the end: one short step is left.
    assert ends == [True, False, False, True]
    assert _math("[m.atEnd(0.8*1.25**7,0.8,1),m.rung(0.8*1.25**7,0.8,1)/0.8]") == [False, pytest.approx(5.0)]


@needs_node
def test_a_notch_or_a_pinch_zooms_and_a_trackpad_scroll_pans():
    # A mouse notch (whole 100 or 120) zooms; a pinch is a Ctrl wheel of small deltas; a two-finger scroll stays native.
    z = "m.zooms"
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:0,deltaY:-100}})") is True
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:0,deltaY:120}})") is True
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:1,deltaX:0,deltaY:3}})") is True
    assert _math(f"{z}({{ctrlKey:true,shiftKey:false,deltaMode:0,deltaX:0,deltaY:-2.5}})") is True
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:0,deltaY:7.5}})") is False
    # A touchpad flick can report a whole number over 50 that is no notch (1679 review): it scrolls, it does not zoom.
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:0,deltaY:63}})") is False
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:0,deltaY:-87}})") is False
    assert _math(f"{z}({{ctrlKey:false,shiftKey:false,deltaMode:0,deltaX:12,deltaY:-100}})") is False
    assert _math(f"{z}({{ctrlKey:false,shiftKey:true,deltaMode:0,deltaX:0,deltaY:-100}})") is False


@needs_node
def test_a_pinch_factor_is_continuous_and_a_notch_is_one_step():
    assert _math("m.factor({ctrlKey:false,deltaMode:0,deltaY:-100})") == pytest.approx(1.25)
    assert _math("m.factor({ctrlKey:false,deltaMode:0,deltaY:100})") == pytest.approx(0.8)
    pinch = _math("m.factor({ctrlKey:true,deltaMode:0,deltaY:-10})")
    assert 1.09 < pinch < 1.12
    assert _math("m.factor({ctrlKey:false,deltaMode:1,deltaY:-3})") == pytest.approx(1.25)


@needs_node
def test_a_release_glides_from_the_last_hundred_milliseconds_and_stops():
    v = _math("m.velocity([{t:0,x:0,y:0},{t:40,x:20,y:0},{t:80,x:40,y:10},{t:100,x:50,y:10}])")
    assert v["x"] == pytest.approx(0.5) and v["y"] == pytest.approx(0.1)
    # A pause before the lift is not a fling.
    assert _math("m.velocity([{t:0,x:0,y:0},{t:30,x:30,y:0},{t:400,x:31,y:0}])") == {"x": 0, "y": 0}
    frames = _math("(()=>{let v=0.8,n=0,d=0;while(!m.settled(v,0)&&n<400){d+=v*16;v=m.decay(v,16);n++}return [n,d]})()")
    assert 20 < frames[0] < 120 and frames[1] > 80


def test_a_gesture_is_a_transform_first_and_the_width_after_one_frame_each():
    # The input paints a transform in the next animation frame; the real width (and the overlay) follows when it goes quiet.
    assert "requestAnimationFrame" in VIEW and "dgm-gesturing" in VIEW and "willChange" in VIEW
    assert "transformOrigin" in VIEW and "translate(" in VIEW
    assert ".dgm-stage.dgm-gesturing" in CSS
    assert "visibility: hidden" in CSS[CSS.index(".dgm-stage.dgm-gesturing") :][:400]


def test_the_picture_takes_the_wheel_the_keyboard_and_a_glide():
    assert "math.zooms(event)" in VIEW and "math.factor(event)" in VIEW
    assert "math.rung(" in VIEW and 'event.key === "1"' in VIEW
    assert "math.velocity(" in VIEW and "math.decay(" in VIEW
    assert "cancelGlide" in VIEW  # a press, a wheel or a key stops it
    assert "reducedMotionWanted()" in VIEW  # the shared motion read (test_motion_resolved), not a raw query


def test_a_pan_settles_a_gesture_first_and_a_slow_glide_is_not_an_edge():
    # 1679 review: the commit anchors on the rectangle taken at the gesture's start, so a drag, a key pan or a glide that moved the
    # scroll in between made the picture jump. Each settles first; the glide keeps a fractional position so a half-pixel step is no edge.
    move = VIEW.index("} else if (points.size === 1 && (roomy()")
    assert "settle();" in VIEW[move : move + 200]
    keys = VIEW.index("const move = {")
    assert "if (move) settle();" in VIEW[keys : keys + 600]
    glide = VIEW[VIEW.index("const glide = (v)") : VIEW.index("const now = ")]
    assert "let [x, y]" in glide and "scrollLeft === x0" not in glide


def test_a_release_under_reduced_motion_stops_dead():
    # L-documents-61: the glide starts only from a pointerup that was moving, and never when less motion is asked for;
    # measured in the app at 4x CPU: 94 px (1440) and 57 px (390, touch) of glide after release, 0 px under reduced motion.
    lift = VIEW[VIEW.index("const lift = (event)") :][:900]
    assert "!reduced()" in lift and "glide(math.velocity(trail))" in lift
    assert "reducedMotionWanted()" in VIEW
