"""INBOX 1686: every mind map node is a perch, not only the boxed ones.

The owner (screenshot of a mind map in the Outline look): "the companion cant sit
on any other mindmap nodes other than the central one". The Outline look draws
the branches plain (`shape: none`), and the board's perch list skipped every
`data-shape="none"` object, so only the pill-shaped centre registered. Measured
(a 13-topic map, Outline): 0 perches before, 12 after, each seat within 0.4px of
the top of the words through zooms of 118 to 260px node width.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _edges_body() -> str:
    js = frontend_text("avatars.js")
    body = js[js.index("nmb.boardEdges = (") :]
    return body[: body.index("\n};\n")]


def test_a_plain_or_underlined_node_is_a_perch_at_its_words() -> None:
    body = _edges_body()
    # The two shapes that draw no box are handled, not skipped.
    assert 'dataset.shape === "none" || el.dataset.shape === "underline"' in body
    assert '.wb-map-text, .wb-text-content' in body
    # The seat is the top of the words, as wide as they are.
    assert "y: w.top, left: w.left, right: w.right" in body
    # A short label (narrower than the 44px box floor) is still a perch.
    assert "w.width < 24" in body


def test_the_box_floor_no_longer_drops_plain_nodes() -> None:
    body = _edges_body()
    # The old line skipped a `none` shape before any other test ran.
    assert 'if (!b || b.width < 44 || b.height < 20 || el.dataset.shape === "none") continue;' not in body


def test_the_seat_on_words_keeps_its_offset_through_a_zoom() -> None:
    js = frontend_text("avatars.js")
    # The few px between a plain node's box and its words scale with the zoom.
    assert "nmb.glue.ty = words.getBoundingClientRect().top - box.top;" in js
    assert "g.dy = g.dy0 + (g.ty * box.width) / g.w0;" in js
