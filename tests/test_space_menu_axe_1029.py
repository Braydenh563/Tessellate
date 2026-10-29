"""Audit 1029 X4: the space menu holds no interactive element inside another.

Measured with axe 4 on the open switcher (scratchpad sweep, 2026-10-29):
aria-required-children (critical) 1 and nested-interactive (serious) 6
before; none after. This test holds the shape that gets there.
"""
from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

HTML = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def _option_fn() -> str:
    js = app_js_text()
    start = js.index("function spaceMenuOption(")
    return js[start : js.index("\n}\n", start)]


def test_the_menu_is_a_menu_not_a_listbox():
    assert 'id="space-menu" class="space-menu glass hidden" role="menu"' in HTML
    assert 'aria-haspopup="menu"' in HTML.split('id="space-switcher-btn"')[1][:200]


def test_a_row_is_a_wrapper_with_the_actions_beside_the_space():
    body = _option_fn()
    assert 'setAttribute("role", "none")' in body
    assert '"menuitemradio"' in body and '"menuitem"' in body
    assert 'document.createElement("span")' in body, "only the actions wrapper is a span"
    assert 'setAttribute("role", "button")' not in body, "a span with a button role inside a button was the finding"
    assert 'role", "option"' not in body
    assert body.index("row.appendChild(option)") < body.index("row.appendChild(actions)")
