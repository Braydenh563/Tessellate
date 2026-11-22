"""The companion's face holds still while the board under it pans or zooms (L-mindmap-24).

mapperf at 500 topics with the companion on: its idle animations (breathe, float, body, blinks)
restyled 137 times in a 30-step pan and the worst pan step went from 35 to 42ms (off) to 94 to
103ms (on). A pan or zoom frame marks it for the gesture, and the rule that already holds the face
still while it is carried holds it then too.
"""
import re

from tests._app_js import frontend_text, JS_DIR

ROOT = JS_DIR.parents[1]


def _fn(src: str, head: str) -> str:
    start = src.index(head)
    return src[start : src.index("\n  }\n", start)]


def test_a_canvas_frame_marks_the_companion_for_the_gesture():
    body = _fn(frontend_text("avatars.js"), "function nameMarkBuddyCanvasZoom(")
    assert 'classList.add("nm-buddy-canvas-moving")' in body
    assert re.search(r'setTimeout\(\(\) => [^;]*classList\.remove\("nm-buddy-canvas-moving"\)', body)


def test_the_carried_rule_holds_the_face_still_for_a_canvas_gesture_too():
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    rule = re.search(r"#nm-buddy:is\(\.nm-buddy-dragging, \.nm-buddy-canvas-moving\) \.name-mark \* \{\s*animation-play-state: paused;", css)
    assert rule, "the face's pause rule does not cover a canvas gesture"
