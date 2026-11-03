"""INBOX 1619 and 1620 (owner, 2026-11-03), each pinned where it was measured."""

from __future__ import annotations

from tests._app_js import frontend_text


def test_tag_popover_closes_instead_of_replacing_when_its_card_was_rerendered():
    src = frontend_text("tag-suggest.js")
    top_up = src[src.index("noteTagChoices(entry).then((more)"):]
    top_up = top_up[: top_up.index("placeHelpPopover(panel, anchor)")]
    assert "!anchor.isConnected" in top_up and "closeNoteTagPopover()" in top_up


def test_constellation_repaints_after_a_resize_even_when_resting():
    src = frontend_text("dash-art.js")
    body = src[src.index("const resync = (entries)"):]
    body = body[: body.index("const observer")]
    assert body.index("p.resizeCanvas") < body.index("scene(")
