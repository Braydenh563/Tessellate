"""INBOX 1508: the chat composer's ResizeObserver measured the box on every
size change, the app's Ctrl +/- zoom included: a forced layout of 75 to 118 ms
a step at 4x CPU, and the zoomed height was saved as one the person had dragged.
Only a pointer resizes a textarea by hand, so the observer acts only while one
is down on the box."""

from __future__ import annotations

from tests._app_js import app_js_text


def _resize_body() -> str:
    js = app_js_text()
    start = js.index("function initComposerResize(")
    return js[start : js.index("\n}\n", start)]


def test_the_observer_returns_unless_a_pointer_is_down_on_the_box():
    body = _resize_body()
    observer = body[body.index("new ResizeObserver(") :]
    assert observer.split("\n")[1].strip() == "if (dragging || !held.pressed) return;"
    assert "held.pressed = true;" in body and "held.pressed = false;" in body
