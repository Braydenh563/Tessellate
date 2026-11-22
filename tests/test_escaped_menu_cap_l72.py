"""L-general-72: an escaped menu taller than either side of its opener was pinned to the window's foot, over its own
button (390x844, Settings, Logs, Sort and view: a 677px list at 157..836 over its opener at 281..325). It now takes the
taller side, capped to that side's room, and scrolls. The sweep (scratchpad/ui-sweeps/menus.js) needs a browser; this
is the source-level ratchet on the cause."""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _place() -> str:
    js = app_js_text()
    return re.search(r"function placeEscapedMenu\(menu, opener\) \{(.*?)\n\}", js, re.S).group(1)


def test_a_menu_too_tall_for_either_side_is_capped_beside_its_opener() -> None:
    body = _place()
    assert "menuSidePlan(box.height, anchor, 4, margin)" in body
    assert "menu.style.maxHeight = `${room}px`" in body
    assert 'menu.style.overflowY = "auto"' in body
    assert "top = plan.up ? anchor.top - 4 - Math.min(box.height, room) : anchor.bottom + 4" in body


def test_the_pin_to_the_foot_is_kept_only_for_an_opener_off_the_window() -> None:
    body = _place()
    assert "const onScreen = anchor.top >= 0 && anchor.bottom <= window.innerHeight" in body
    assert body.index("else if (onScreen)") < body.index("} else top = Math.max(margin, window.innerHeight - margin")


def test_a_cap_from_an_earlier_open_is_cleared_first() -> None:
    body = _place()
    assert body.index("if (menu._escapeCap)") < body.index("const box = menu.getBoundingClientRect()")
