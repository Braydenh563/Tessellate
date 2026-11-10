"""W30 (OPEN.md, 2026-11-09 work order): a board render with many map links pays for each link once.

Measured at 4x CPU on a 500-topic map with 300 cross-links (render, median of 5): nothing changed
1,361 to about 340 ms, one topic moved 1,501 to about 300 ms. The profile put 7.4 s of 12 renders in
`querySelector` (each link end walked the page for its topic's box) and 4.8 s in
`wbMapCrossLinkLook`, which one render asked for three times per link."""

from tests._app_js import frontend_text


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_the_render_measures_every_topic_in_one_walk_before_the_links():
    js = frontend_text("whiteboard.js")
    body = _between(js, "function renderWhiteboard() {", "sketchSelection.exit().remove();")
    walk = body.index("wbIndexMapNodeElements()")
    assert body.index("const strokeInk") < walk < body.index("sketchUpdate.each(function(d) {")
    assert "wbIsMap() && wbState.sketches?.length" in body[walk - 60 : walk + 10]


def test_a_links_look_is_found_once_per_pass_and_keyed_on_its_ends():
    js = frontend_text("whiteboard-map.js")
    look = _between(js, "function wbMapCrossLinkLook(parsed) {", "wbMapCrossLinkLook.built = function (")
    assert "looks: new Map()" in js
    # Both ends' place and box are in the key, so a node moved between two asks in one task is
    # never answered with the old line; a branch laid out as a block is not kept at all.
    for part in ("source.x", "target.x", "sourceBox.w", "targetBox.h", "parsed.bend", "sourceAnchor"):
        assert part in look, part
    assert "!source._bl && !target._bl && target._blTop == null" in look
    assert "wbMapCrossLinkMemo.looks.get(stamp)" in look
