"""The app shell keeps its rows on one line at every zoom (owner, 2026-11-11).

"make sure the wrapping and ui issues arent an issue anywhere else from zoom
or resolution." `scratchpad/ui-sweeps/wrapzoom-shell.js` measured the shell
over nine viewports (1280 to 2560 at 100%, and 1920 at 125, 150 and 200%)
and 768x1024. `scratchpad/ui-sweeps/dashedit-zoom.js` measures these fixes.
What a static test can pin is pinned here; the rings are in
`tests/test_ring_room.py`.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR
from tests._css_paths import css_text

CSS = css_text()
#: dashboard.js is lazy (not in the boot scripts `app_js_text()` reads).
JS = (JS_DIR / "dashboard.js").read_text(encoding="utf-8")


def _body(selector: str) -> str:
    """The declarations of the rule whose selector is exactly `selector`."""
    m = re.search(r"(?:^|[}/])\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", CSS, re.M)
    assert m, f"no rule for {selector}"
    return m.group(1)


def _edit_head_block() -> str:
    start = re.search(r"if \(dashEditMode\) \{\s+const controls", JS).start()
    return JS[start : JS.index("card.appendChild(header);", start)]


def test_an_edit_layout_widget_head_is_one_line():
    """34 of 35 heads wrapped (32 -> 66px at 1366): five controls at 293px
    beside the title. The head stays one line; the title gives way."""
    assert re.search(r"flex-wrap:\s*nowrap", _body(".dash-widget > .row.space-between:has(> .dash-edit-actions)"))
    title = _body(".dash-widget > .row:has(> .dash-edit-actions) > h2")
    for want in (r"min-width:\s*0", r"text-overflow:\s*ellipsis", r"white-space:\s*nowrap", r"overflow:\s*hidden"):
        assert re.search(want, title), want
    assert re.search(r"flex:\s*none", _body(".dash-edit-actions"))


def test_the_edit_head_folds_its_lesser_controls_into_a_kebab():
    """Row actions (DESIGN.md): one action stays, the rest are the ⋯'s rows,
    never a strip of buttons that wraps under the title."""
    block = _edit_head_block()
    assert "kebabMenu(items" in block
    assert "Move earlier" in block and "Move later" in block
    assert block.count("smallButton(") == 1, "only the Remove (or Add) glyph stands in the head"
    assert '"ph:x"' in block and '"ph:plus"' in block, "Remove and Add are their glyphs, named by their titles"
    assert "title.title = " in block, "a cut title is whole on hover"
    assert '" Drag"' not in block, "the grip is its glyph"


def test_a_quick_edit_tile_leaves_room_for_its_menu_button():
    """At 768 the button is 44px (`--target-min` under touch) and a fixed
    `--space-9` (32px) left 17px of "Ask your notes" under it."""
    body = _body(".quick-edit-tile > .quick-link")
    assert re.search(r"padding-right:\s*calc\(var\(--target-min\)", body), "the room follows the button's own size"


def test_the_header_ring_offset_spares_the_panel_grip():
    """The header's 1px ring offset reached the notifications panel's grip,
    whose ring the panel then cut by 3px; the grip keeps its inset ring."""
    assert "button:not(.panel-grip):focus-visible" in CSS
    assert re.search(r"\.panel-movable-on > button\.panel-grip:focus-visible\s*\{[^}]*outline-offset:\s*-2px", CSS)
