"""Source text: an animation's keyframes and the class that starts it are CSS and JS text; the fade was measured in Chromium at merge.

L414: a Notes sub-tab panel cross-fades, only on a switch inside Notes.

`@starting-style` cannot tell a section switch from the page arriving (the
page already fades, `.tab-page:not(.hidden)`), so `showNotesSection` marks the
page for a moment when the Notes tab is already on screen, and the panel's
fade is keyed on that mark.
"""

from pathlib import Path

from tests._app_js import frontend_text

NAV = frontend_text("navigation.js")
CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")


def test_the_switch_sets_and_clears_the_mark():
    body = NAV[NAV.index("function showNotesSection(") :][:6000]
    assert 'classList.add("section-switch")' in body
    assert 'classList.remove("section-switch")' in body


def test_the_fade_needs_the_mark():
    at = CSS.index("#tab-notes.section-switch")
    block = CSS[at - 200 : at + 900]
    assert "@starting-style" in block and "opacity: 0.4" in block
