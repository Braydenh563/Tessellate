"""Source text: the map strip's icon buttons, its doors and the drawing bar's
tool buttons sit on the control height tokens; Reset measured 28 by 44 at 390
because its width stayed 1.75rem under the 44px touch floor (L-ui-modernisation-38)."""

import re

from tests._app_js import frontend_text


def _rule(css, selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_map_strip_icon_buttons_stay_round_under_the_touch_floor():
    """Source text: width follows the touch floor too, or Reset measured 28 by 44."""
    rule = _rule(frontend_text("css/07-whiteboard-misc.css"), ".wb-map-strip > button.icon-only")
    assert "height: var(--control-h-dense)" in rule
    assert "width: max(var(--control-h-dense), var(--target-min))" in rule


def test_map_strip_doors_and_tool_group_use_tokens():
    """Source text: the doors and the drawing bar's tool buttons are on the tokens."""
    door = _rule(frontend_text("css/07-whiteboard-misc.css"), ".wb-map-strip .wb-menu-toggle")
    tool = _rule(frontend_text("css/06-timeline-dialogs.css"), ".wb-tool-group button")
    assert "height: var(--control-h-dense)" in door and "1.75rem" not in door
    assert "width: var(--control-h-body)" in tool and "height: var(--control-h-body)" in tool
