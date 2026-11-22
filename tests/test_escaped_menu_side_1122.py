"""Source text: the menu sweep at 390x844 (2026-11-22): Settings Logs More (679px) fitted neither under
nor over its button and was pushed up into the window over it (top 157 against the button's 281 to 325).
An escaped menu now takes the one side rule, `menuSidePlan`, and scrolls inside its cap (top 329, under the button).
"""

from __future__ import annotations

from pathlib import Path

MENUS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = MENUS.index(f"function {name}(")
    depth = 0
    for i in range(MENUS.index("{", start), len(MENUS)):
        depth += MENUS[i] == "{"
        depth -= MENUS[i] == "}"
        if depth == 0:
            return MENUS[start : i + 1]
    raise AssertionError(name)


def test_an_escaped_menu_that_fits_neither_side_is_capped_not_pushed_over_its_button() -> None:
    place = _fn("placeEscapedMenu")
    assert "menuSidePlan(box.height, anchor" in place
    assert 'menu.style.overflowY = plan.cap === null ? "" : "auto";' in place
    # The old fallback pinned the whole box inside the window, wherever its button was.
    assert "window.innerHeight - margin - box.height)" not in place
