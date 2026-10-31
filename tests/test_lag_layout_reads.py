"""INBOX 1426: opening the whiteboard forced the board's first layout inside
`initWhiteboard` (three panel measurements and the toast lift, 148ms at a 4x
throttle). The panel metrics come from the ResizeObserver, which reports after
layout, and tell their listeners before they write."""

import re

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


# INBOX 1446 (the owner's lag log, 2026-10-29): the worst frames were forced
# layouts from a read after a write inside a loop, one layout per pass. A loop
# body that both writes what the page lays out and reads a measurement is that
# shape; the sites below read first, or write after, instead.
_READS = re.compile(r"\.(?:offset(?:Height|Width|Top|Left)|client(?:Height|Width)|scroll(?:Height|Width)|getBoundingClientRect)\b|getComputedStyle\(|\.getAnimations\(")
_WRITES = re.compile(r"\.hidden\s*=|\.classList\.(?:add|remove|toggle)\(|\.style\.\w+\s*=|\.textContent\s*=|\.append(?:Child)?\(|\.setAttribute\(|\.dataset\.\w+\s*=|\.animate\(|\.scroll(?:Top|Left)\s*[-+]?=(?!=)")


def _braced(js: str, start: int) -> str:
    """The `{ ... }` block whose opening brace is the first one at or after `start`."""
    i = js.index("{", start)
    depth = 0
    for j in range(i, len(js)):
        depth += {"{": 1, "}": -1}.get(js[j], 0)
        if depth == 0:
            return js[i : j + 1]
    raise AssertionError("unbalanced braces")


def _loop_bodies(fn_source: str):
    for m in re.finditer(r"\b(?:for|while)\s*\(", fn_source):
        rest = fn_source[m.end() :]
        depth, k = 1, 0
        while depth and k < len(rest):
            depth += {"(": 1, ")": -1}.get(rest[k], 0)
            k += 1
        # A loop without braces is one statement: not a read-after-write pass.
        if rest[k:].lstrip().startswith("{"):
            yield _braced(rest, k)


def mixed_loops(file: str, fn: str) -> list[str]:
    """Loop bodies in `fn` that write the page and also measure it."""
    js = frontend_text(file)
    body = _braced(js, js.index(f"function {fn}("))
    return [b for b in _loop_bodies(body) if _WRITES.search(b) and _READS.search(b)]


#: (file, function) pairs fixed under INBOX 1446; the next one found goes here.
READ_THEN_WRITE_SITES = [
    ("timeline-calendar.js", "timelineCalFit"),
    ("avatars.js", "nameMarkBuddyBlend"),
    ("library.js", "keepLibraryScroll"),
]


def test_named_lag_sites_do_not_measure_inside_a_writing_loop():
    for file, fn in READ_THEN_WRITE_SITES:
        assert mixed_loops(file, fn) == [], f"{file} {fn}: batch the reads before the writes"


def test_timeline_ticks_take_the_strip_height_from_the_observer():
    """A draw writes the strip and asks for ticks in the same task: a `clientHeight` read
    there laid the page out (248ms in the owner's log). The observer's number is free."""
    js = frontend_text("timeline-ticks.js")
    body = _braced(js, js.index("async function timelineTicks("))
    assert "contentRect.height" in body
    reads = [m.group(0) for m in re.finditer(r"^(?!\s*//)[^\n]*clientHeight[^\n]*", body, re.M)]
    assert reads == ["  const height = timelineTickCache.height ?? strip.clientHeight;"], reads


def test_a_pointer_picked_tab_finds_its_scroller_after_it_has_drawn():
    """`switchTab` awaits before it reveals the page, so a lookup made inside the click found
    the target page still hidden, returned nothing and never moved the focus (measured: the
    focus stayed on the button on every tab). Found two frames on, size test before style."""
    js = frontend_text("phone-shell.js")
    body = _braced(js, js.index("function focusTabPage("))
    assert re.search(r"afterFrames\(\(\) => \{.*tabPageScroller\(.*\}\);", body, re.S)
    scroller = _braced(js, js.index("function tabPageScroller("))
    assert scroller.index("scrollHeight > el.clientHeight") < scroller.index("getComputedStyle(el)")


def test_card_chips_are_fitted_once_after_they_are_all_in():
    """Each chip was inserted and then its line fitted, which reads widths: a layout per card
    (105 layouts in six note jumps at 4x CPU, 800ms). `fitNoteMetas` takes a list for this."""
    js = frontend_text("notes-list.js")
    body = _braced(js, js.index("function ensureOneCardCount("))
    assert not [b for b in _loop_bodies(body) if "fitNoteMetas(" in b], "fit after the loop, once"
    assert "fitNoteMetas(fitted)" in body
