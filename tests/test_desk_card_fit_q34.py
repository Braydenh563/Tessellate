"""Q34 (the desktop pet outside the window): the card window, the companion's window where the
see-through figure is not used (macOS, or Windows when the overlay fails), fits its menu.

Measured 2026-11-11 with a fake pywebview host whose set_size resizes the page: the six-row menu
scrolled 95 px inside the fixed 248 by 312 window and the context menu 24 px inside 248 by 268;
after, the page asks for 248 by 408 and 248 by 311 and neither scrolls, at device scale 1 and 2.
The window itself (on top, transparency, placement) is a real-desktop check this cannot make."""

# ruff: noqa: F811  (pytest fixtures are used by name)
from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import made, prefs  # noqa: F401

JS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n  }\n", start)]


def test_the_card_window_asks_for_the_menus_measured_height_not_the_fixed_guess() -> None:
    fit = _body("fit")
    assert re.search(r'else if \(state === "menu" \|\| state === "context"\) height = cardHeight\(', fit), fit


def test_the_card_height_is_the_panel_plus_the_companion_and_the_gap_rounded_up() -> None:
    card = _body("cardHeight")
    assert 'getBoundingClientRect().height' in card and "rowGap" in card
    assert "Math.ceil(panelHeight(" in card and "+ pet + gap" in card
    # No layout to measure (a hidden page): the old fixed size, never a zero-height window.
    assert "return fallback" in card


def test_the_measured_card_menu_height_reaches_the_window(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    window = made.webview.made[0]
    assert not made.panel  # the card window, not the overlay's panel
    assert window.options["js_api"].set_size(248, 408, "menu") == [248, 408]
    assert ("resize", 248, 408) in window.calls
