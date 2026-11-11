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
from tests._js_scope import unwrapped


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


def test_the_companion_notes_foot_keeps_one_row():
    """Wrap: the companion's 296px note foot held Note | To-do, the picture,
    Close and Save in 323px, so Save wrapped (foot 102px at every scale). The
    window's head X is the card's Close, so the foot's is folded into it."""
    assert "display: none;" in _block("desk-companion-lazy.css", '#desk-capture .capture-card-foot > [data-cc="close"]')
    js = (CSS_DIR.parent / "js" / "desk-companion.js").read_text(encoding="utf-8")
    hand = js[js.index('querySelectorAll("[data-desk-close]")'):][:400]
    assert '[data-cc="close"]' in hand and "cardClose.click()" in hand, "the head X closes the card the card's way"


def test_a_quiet_settings_button_outdents_only_where_there_is_room():
    """Clip and overlap: the -8px outdent ran Reset appearance to defaults and
    Read it again 4px past the pane's ring room, and pulled Clear kept pages'
    tint over the word before it. A row straight under a section and a button
    inside a sentence keep their own box, in the Settings window and the
    generated Appearance panel alike."""
    want = re.compile(r":is\(\.settings-section > \.row, p\) > button\.ghost[^{]*\{\s*margin-inline-start: 0;")
    assert want.search(_css("settings-controls-lazy.css"))
    assert want.search(_css("appearance-panel-lazy.css")), "run scripts/appearance_panel_css.py"


def test_a_settings_panes_lone_actions_stand_a_ring_below_the_top():
    """Clip: at 768 the pane dock gives its row up and its actions sit at the
    pane's top, flush with the scroller's edge, so their rings lost 4px."""
    css = _css("settings-controls-lazy.css")
    block = css[css.index("h3.jump-echo:only-child) > .dock-actions {"):].split("}", 1)[0]
    assert "inset-block-start: var(--ring-room);" in block


def test_an_icon_pickers_track_is_never_narrower_than_its_button():
    """Overflow: at 768 the touch floor made the square buttons 44px in
    39.8px tracks, and the last one stood 4px out of New space's picker."""
    block = _block("07-whiteboard-misc.css", ".space-icon-picker")
    assert "minmax(max(2.25rem, var(--target-min)), 1fr)" in block


def test_a_settings_nav_group_link_keeps_one_line():
    """Wrap: "Use these tools from another app" ran to two lines in its 212px
    link. One line, an ellipsis, and the whole name in the title."""
    block = _block("01-forms-settings.css", "#settings-nav .settings-nav-group")
    for line in ("white-space: nowrap;", "text-overflow: ellipsis;", "overflow: hidden;"):
        assert line in block
    js = unwrapped((CSS_DIR.parent / "js" / "settings-find.js").read_text(encoding="utf-8"))
    assert "link.title = label;" in js


def test_a_background_style_cards_facts_keep_one_line():
    """Wrap: one card's chip and cost split onto two lines (42.6px against
    20px) because the facts were a Settings `.row`, which wraps by id."""
    block = _block("02-chat-graph.css", ".bg-style-facts")
    assert "flex-wrap: nowrap;" in block
    assert "text-overflow: ellipsis;" in _block("02-chat-graph.css", ".bg-style-facts > .theme-note")
    js = (CSS_DIR.parent / "js" / "settings.js").read_text(encoding="utf-8")
    assert 'facts.className = "bg-style-facts";' in js
