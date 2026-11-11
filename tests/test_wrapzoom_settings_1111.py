"""Settings, its dialogs and the desktop companion hold one line at every zoom.

The owner, 2026-11-11: "make sure the wrapping and ui issues arent an issue
anywhere else from zoom or resolution". `scratchpad/ui-sweeps/wrapzoom-settings.js`
measured Settings, every shell dialog and /desktop-companion.html across ten
viewports (1280 to 2560 at 1x, 1920 at 125, 150 and 200%, 2560 at 200%, 768)
and found each defect below at every one of them, so none of them was a zoom
accident: each was a rule. These lints pin the rules; the sweep is the proof.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS_DIR / name).read_text(encoding="utf-8"), flags=re.S)


def _block(name: str, selector: str) -> str:
    text = _css(name)
    at = text.index(selector + " {")
    return text[at:].split("}", 1)[0]


def test_a_number_in_a_setting_row_is_a_numbers_width():
    """Wrap: the base field rule (`input[type=number]`, width 100%) took the
    694px pane, so Run budget's two fields and Keep this many backups dropped
    under their labels (rows 121px and 73px tall at 1280 to 2560)."""
    assert "width: 8rem;" in _block("04-chat-dock-appearance.css", ".setting-row > input[type=\"number\"].setting-control")
    retention = _block("02-chat-graph.css", "input.backup-retention-input")
    assert "width: 5rem;" in retention, "a bare class loses to input[type=number] (0,1,1)"
    assert "flex: 1 1 auto;" in _block("02-chat-graph.css", "#settings-modal #backup-retention-row > label")
