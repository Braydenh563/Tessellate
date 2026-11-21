"""L-documents-1: the diagram picture pans by dragging with the right mouse button.

The middle button and Space already pan (diagram-view.js). The right button joins them: a press that
travels over 12 px pans, and the menu the same button opens (a block's or an arrow's) is held back for
that drag, so only a right press that stays put opens it. Decision: the diagram builder pans with the
right button, as draw.io does (the whiteboard's own decision 258 is its own).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "frontend" / "js" / "diagram-view.js").read_text(encoding="utf-8")


def test_the_right_button_starts_a_pan_like_the_middle_one():
    assert "event.button !== 1 && event.button !== 2" in VIEW
    assert "rightDrag = event.button === 2" in VIEW


def test_a_right_drag_holds_back_the_menu_and_closes_one_already_open():
    assert 'fig.addEventListener("contextmenu", (event) => {' in VIEW
    held = VIEW[VIEW.index('fig.addEventListener("contextmenu"') :][:420]
    assert "rightDrag && travel > 12" in held and "event.preventDefault()" in held and "event.stopImmediatePropagation()" in held
    assert "if (rightDrag && travel > 12) closeActionMenus();" in VIEW


def test_the_guide_says_which_buttons_pan():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    assert "Space and drag, or right-drag, pans" in body
