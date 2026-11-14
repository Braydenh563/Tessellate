"""L543: Ctrl+Z reaches the OCR workspace's own acts (Delete this reading) from inside it.

The undo sweep (scratchpad/ui-sweeps/undo.js, surface "ocr workspace") found the
delete on the stack and Ctrl+Z doing nothing: the workspace is a `.modal-overlay`,
which `behindModal` read as a confirm in front. Its acts are steps on the stack,
as Settings' are; a confirm over it still pauses the chord.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

WIRING = (JS_DIR / "settings-wiring.js").read_text(encoding="utf-8")


def _pause_selector() -> str:
    match = re.search(r'const behindModal = \(\) => \[\.\.\.document\.querySelectorAll\("([^"]+)"\)\]', WIRING)
    assert match, "behindModal's selector"
    return match.group(1)


def test_the_ocr_workspace_is_not_a_pause_for_undo():
    assert ":not(#settings-modal):not(#ocr-workspace)" in _pause_selector()


def test_any_other_overlay_or_open_dialog_still_pauses():
    parts = [p.strip() for p in _pause_selector().split(",")]
    assert parts[0].startswith(".modal-overlay:not(") and "dialog[open]" in parts
