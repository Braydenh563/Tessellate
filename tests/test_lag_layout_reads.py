"""INBOX 1426: opening the whiteboard forced the board's first layout inside
`initWhiteboard` (three panel measurements and the toast lift, 148ms at a 4x
throttle). The panel metrics come from the ResizeObserver, which reports after
layout, and tell their listeners before they write."""

from tests._app_js import frontend_text


def _panel_metrics_block() -> str:
    js = frontend_text("whiteboard.js")
    start = js.index("const publish = (entries) =>")
    return js[start : js.index("new ResizeObserver(publish).observe(panel);", start)]


def test_panel_metrics_are_not_measured_synchronously_at_init():
    js = frontend_text("whiteboard.js")
    start = js.index("const publish = (entries) =>")
    tail = js[start : start + 1500]
    assert "      publish();\n" not in tail
    assert "borderBoxSize" in _panel_metrics_block()


def test_listeners_are_told_before_the_property_is_written():
    block = _panel_metrics_block()
    assert block.index("wb-panel-resize") < block.index("setProperty")


def test_toast_lift_is_not_run_synchronously_at_init():
    js = frontend_text("whiteboard.js")
    i = js.index('window.addEventListener("resize", liftToasts);')
    assert js[i : i + 80].count("liftToasts();") == 0


def test_skeleton_memory_stops_measuring_at_the_fold():
    js = frontend_text("notes-list.js")
    body = js[js.index("function skeletonRemember"):]
    body = body[: body.index("\n}\n")]
    assert "break;" in body
    assert "rows.filter" not in body
