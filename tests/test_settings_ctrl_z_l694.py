"""L694: Ctrl+Z reaches a Settings change from inside Settings and from a focused switch."""

from __future__ import annotations

from tests._app_js import JS_DIR

WIRING = (JS_DIR / "settings-wiring.js").read_text(encoding="utf-8")
CONTROLS = (JS_DIR / "settings-controls.js").read_text(encoding="utf-8")


def test_the_settings_dialog_is_not_a_pause_for_undo():
    assert '.modal-overlay:not(#settings-modal), dialog[open]' in WIRING


def test_a_focused_switch_or_slider_does_not_keep_the_chord():
    assert 'input[type=checkbox],input[type=radio],input[type=range]' in WIRING


def test_a_learning_switch_is_a_step_on_the_stack():
    assert 'pushRequestUndo("Learning switch", "/learned/switches", "PUT"' in CONTROLS
