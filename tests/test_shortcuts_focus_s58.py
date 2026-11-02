"""Audit 1028 S58: closing the shortcuts sheet gives focus back to what opened it.

Measured 2026-11-02 (s58b sweep): Shift+? from #settings-btn, then Escape, left
focus on BODY; Settings, the palette, Find, privacy and Quit all returned it.
The sheet now keeps its opener on the overlay element (no new global) and
closes through `focusBackTo`, the helper the palette and notifications use.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def test_the_sheet_remembers_its_opener_and_gives_focus_back():
    js = app_js_text()
    opener = js[js.index("function openShortcuts() {") :]
    opener = opener[: opener.index("\n}\n")]
    assert 'overlay.returnFocus = document.activeElement' in opener
    closer = js[js.index("function closeShortcuts() {") :]
    closer = closer[: closer.index("\n}\n")]
    assert 'focusBackTo(overlay.returnFocus, "#tab-bar [aria-selected=\'true\']")' in closer
    assert "overlay.returnFocus = null" in closer
