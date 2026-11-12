"""INBOX 1643: an idle graph asks for no frames ("raf 439ms on graph:
gcRequestDraw 54 calls/s" for 10 s). Measured in the app by Playwright: 0 calls,
0 draws and 0 rAF callbacks a second 12 s after the layout settled, at 36 and
336 notes; the stuck state itself did not reproduce, so the guard is structural:
every frame the draw asks for itself (a hover ease, a fade, a glide, a fade-in,
a composed hover frame) counts toward one bound, and a request from outside the
draw starts the count again."""

from __future__ import annotations

from tests._app_js import frontend_text
from tests._js_scope import gc_frame


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start)]


def test_the_draw_loop_rearms_only_on_motion_and_is_bounded():
    src = frontend_text("js/graph-canvas.js")
    assert "gcRequestDraw.selfCap = 300;" in src
    draw = gc_frame(src)
    # All four things a frame asks for itself count; none is exempt.
    assert "if (easing || fading || gliding || s.bornPending) {" in draw
    assert "!gliding && !s.bornPending) {" not in draw
    tail = draw[draw.index("s.selfFrames = (s.selfFrames || 0) + 1;") :]
    stop = tail.index("s.selfFrames > gcRequestDraw.selfCap")
    # The bound is checked before any self-request, and the requests are
    # still guarded by the motion flags (no unconditional re-arm).
    assert stop < tail.index("gcRequestDraw(s, true)") < tail.index("gcRequestDraw(s);")
    assert "else if (easing || fading || gliding || s.bornPending) gcRequestDraw(s);" in tail
    assert "if (cheap && (easing || busy)) gcRequestDraw(s, true);" in tail


def test_the_composed_hover_frame_counts_toward_the_same_bound():
    composed = _fn(frontend_text("js/graph-canvas.js"), "gcDrawComposed")
    assert "moving && (s.selfFrames = (s.selfFrames || 0) + 1) <= gcRequestDraw.selfCap" in composed
    assert "gcRequestDraw(s, true);" in composed
    assert "s.drawAsking = true;" in composed


def test_an_outside_request_starts_the_count_again():
    fn = _fn(frontend_text("js/graph-canvas.js"), "gcRequestDraw")
    assert "if (!s.drawAsking) s.selfFrames = 0;" in fn
    # The only caller that raises the flag is the draw itself.
    src = frontend_text("js/graph-canvas.js")
    assert src.count("s.drawAsking = true;") == 2
