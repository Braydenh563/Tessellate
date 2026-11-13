"""Source text: the theme button opens the Appearance panel on a right-click, a door
nothing on screen showed; its tooltip and the Appearance help now say so (L-ui-modernisation-40)."""

from tests._app_js import frontend_text


def test_the_theme_tooltip_names_the_appearance_door():
    """Source text: its tooltip and the Appearance help now say so."""
    js = frontend_text("js/settings.js")
    assert '$("theme-btn").addEventListener("contextmenu"' in js and "openAppearancePanel()" in js
    assert "Right-click for Appearance`" in js


def test_the_appearance_help_names_the_right_click():
    """Source text: the Appearance help now says so."""
    from tessellate.ai.help_topics_core import HELP_TOPICS

    topic = next(t for t in HELP_TOPICS if t["id"] == "appearance")
    assert "right-click the theme button" in topic["body"]
