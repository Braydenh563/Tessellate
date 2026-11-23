"""Source text: at 390 the phone shell moves the note picker into the dock's
attach group beside #attach-image (phone-shell.js), so the dock's pill rule in
04-chat-dock-appearance.css must reach the picker's button too (L441).

Measured before: #attach-image 999px (the dock pill), #attach-note 4.8px (the
plain button corner), side by side at y 713.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "04-chat-dock-appearance.css"


def test_the_moved_note_picker_button_takes_the_dock_pill():
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    rule = next(m for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css) if "border-radius: var(--radius-pill)" in m.group(2) and ".chat-dock-controls>.chat-tool-group>button" in m.group(1))
    selectors = [s.strip() for s in rule.group(1).split(",")]
    assert ".chat-dock-controls .note-picker>button" in selectors
