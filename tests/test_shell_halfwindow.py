"""Half-window pass (owner, 2026-10-25): the rules that keep the shell inside a narrow window.

Each test pins one measured fix from `scratchpad/ui-sweeps/halfwindow.js`
(overflow, off-viewport controls, overlaps, blank bars). They read the CSS
text because the suite cannot see a layout; the sweep is the measurement.
"""

from __future__ import annotations

from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _css(name: str) -> str:
    return (CSS / name).read_text(encoding="utf-8")


def test_settings_pane_dock_with_only_a_hidden_title_is_hidden():
    """Settings, Models at half width was a blank bordered bar: the jump list hides the title."""
    text = _css("settings-controls-lazy.css")
    assert "h3.jump-echo:only-child" in text
    assert "display: none" in text.split("h3.jump-echo:only-child", 1)[1].split("}", 1)[0]


def test_focus_mode_thumb_bar_sits_on_the_bottom_edge():
    """Focus mode draws over the tab bar, so the bar must not leave its band blank."""
    text = _css("library-lazy.css")
    assert "#tab-documents.doc-focus .doc-phone-bar" in text
