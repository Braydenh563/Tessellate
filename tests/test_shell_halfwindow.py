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


def test_note_row_end_cluster_is_in_the_flow_under_600():
    """The note's menu button stood on its time and hung below the card (measured at 560)."""
    text = _css("10-responsive.css")
    block = text.split("#entry-list > li :is(.entry-actions, .entry-meta-end) {", 1)[1].split("}", 1)[0]
    assert "position: static" in block
    assert "#entry-list > li .menu-wrap > button" in text


def test_answer_folds_are_flat_not_boxed_buttons():
    """Sources, Grounded in and Why this answer sit in a framed card: no resting box."""
    text = _css("07-whiteboard-misc.css")
    assert ":not(.fold-summary) {" in text


def test_chat_suggestions_wrap_under_600_instead_of_fading():
    text = _css("08-consistency.css")
    block = text.split("  .chat-empty #chat-suggest > .chip {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in block
    assert "overflow-x: auto;\n    scrollbar-width: none;\n    mask-image" not in text.split("choice controls, the owner", 1)[0]


def test_ask_box_hides_the_lone_sparkle_and_the_model_picker_takes_the_row():
    assert ".ask-composer-icon {\n    display: none;" in _css("08-consistency.css")
    assert "max-width: none;" in _css("10-responsive.css").split("#ask .ask-header-actions > .select-shell:has(#ask-feature-model)", 1)[1].split("}", 1)[0]


def test_documents_dock_closes_up_so_the_more_menu_stays_on_the_row():
    text = _css("library-lazy.css")
    block = text.split("dock's own share of a 44px target stays. */\n", 1)[1].split("\n}\n", 1)[0]
    assert "column-gap: var(--space-1)" in block
    assert ".doc-view-cluster .seg > button" in block


def test_companion_blocks_browser_touch_scroll_so_a_drag_is_not_cancelled():
    text = _css("08-consistency.css")
    assert "#nm-buddy { transition: opacity var(--motion-base) var(--ease-out); touch-action: none; }" in text


def test_ask_header_group_shrinks_and_wraps_instead_of_running_past_the_card():
    text = _css("01-forms-settings.css")
    block = text.split("#ask > .row.space-between > .ask-header-actions {", 1)[1].split("}", 1)[0]
    assert "flex: 1 1 auto" in block and "min-width: 0" in block
