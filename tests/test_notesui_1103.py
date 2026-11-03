"""INBOX 1619 and 1620 (owner, 2026-11-03), each pinned where it was measured."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent


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


def test_manage_panels_scroll_the_tidy_box_and_the_rows_together():
    css = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    scroller = css[css.index(".manage-cat-scroll {") :].split("}", 1)[0]
    assert "overflow-y: auto" in scroller
    assert "overflow-y" not in css[css.index(".manage-cat-list {") :].split("}", 1)[0]
    for name in ("categories-panel.js", "tag-manager.js"):
        assert "manageScroll(suggest, list)" in frontend_text(name)
