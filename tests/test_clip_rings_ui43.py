"""Source text: clip685 390 dark found the capture card's swatch focus ring
drawn 8.4px past a 4.8px padding inside `.swatch-picker`, whose
`overflow-x: auto` clips both axes. The padding now holds the ring:
outline-offset `--space-1 + 4px` plus the 2px outline (L-ui-modernisation-43)."""

import re

from tests._app_js import frontend_text


def _rule(css, selector):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_swatch_picker_padding_holds_the_focus_ring():
    """Source text: the padding holds the whole focus ring."""
    picker = _rule(frontend_text("css/capture-card-lazy.css"), ".capture-card-colours .swatch-picker")
    ring = _rule(frontend_text("css/04-chat-dock-appearance.css"), ".swatch-option:focus-visible")
    assert "overflow-x: auto" in picker
    assert "outline: 2px" in ring and "outline-offset: calc(var(--space-1) + 4px)" in ring
    assert "padding: calc(var(--space-1) + var(--ring-room) * 1.5)" in picker


def test_dialog_head_title_clips_on_x_only():
    """Source text: overflow-x: clip fixes it; `hidden` cut an accented capital's ink."""
    title = _rule(frontend_text("css/07-whiteboard-misc.css"), ".dialog-head .dialog-head-title")
    assert "overflow-x: clip" in title and "overflow: hidden" not in title
    assert "text-overflow: ellipsis" in title


def test_scroll_row_arrow_ring_is_drawn_inside():
    """Source text: the end arrow's ring was clipped 3.6px by its scroller at 390."""
    rule = _rule(frontend_text("css/00-tokens-shell.css"), "button.scroll-row-arrow:focus-visible")
    assert "outline-offset: -2px" in rule
