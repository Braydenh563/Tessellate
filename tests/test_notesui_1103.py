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


def test_note_edit_form_head_uses_the_cards_gap_tokens():
    misc = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    title = misc[misc.index(".entry-list input.note-edit-title {") :].split("}", 1)[0]
    assert "padding: var(--space-2) var(--space-4) var(--space-1);" in title
    side = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    meta = side[side.index(".note-edit-meta {") :].split("}", 1)[0]
    assert "padding: 0 var(--space-4) var(--space-2);" in meta
