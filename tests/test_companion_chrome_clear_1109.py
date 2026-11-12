"""The in-app companion keeps its whole box off the chrome's controls (blind test bt-compcomp-1109, items 20, 23).

Measured before (1440x900, Atlas, six tabs, 4 s after each tab click): the tuck behind the status bar sat at
x 1284 with its 64x92 box over the bar's forward and history buttons (28x15 each), and on Chat over the
`ai-unavailable` chip (64x29); the earlier blind run had 1044..1108 over Agent and Guide. After: 0 overlaps on all six
tabs (`rectHits` skips a peek whose box meets a control; a bar with no clear stretch still takes the old check).
The companion's face is a real `<button>` with a name, so it is a tab stop: item 23 measured the wrapper.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))


def _rect_hits() -> str:
    start = AV.index("rectHits: (x, y, obstacles) =>")
    return AV[start : AV.index("\n", start)].replace("rectHits:", "const rectHits =").rstrip(",") + ";"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_rect_hits_measures_the_whole_box() -> None:
    script = f"const NMB_W = 64, NMB_H = 92;\n{_rect_hits()}\n" + (
        "const bar = [{ left: 1044, right: 1076, top: 868, bottom: 883 }];"
        "console.log(JSON.stringify([rectHits(1044, 791, bar), rectHits(1000, 791, bar), rectHits(1012, 791, bar), rectHits(1100, 791, bar), rectHits(1044, 700, bar), rectHits(1044, 791, [])]));"
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # over; 20px over; 12px over; clear right; clear above; no obstacles
    assert out == [True, True, True, False, False, False]


def test_a_peek_that_meets_a_control_is_skipped_then_relaxed() -> None:
    assert re.search(r'perch\.legs === "peek" && nmb\.rectHits\(perch\.x, perch\.y, obstacles\)\) continue;', AV)
    assert "!nmb.rectHits(spot.x, spot.y, obstacles) && fits(spot)) || pool.find(fits)" in AV
    assert "fallbacks.filter((f) => !nmb.rectHits(f.x, f.y, obstacles)), ...fallbacks" in AV


def test_the_face_is_a_named_button_with_a_menu_key() -> None:
    assert 'const face = document.createElement("button");' in AV
    assert 'event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)' in AV
    assert "Shift+F10 for its menu" in AV


def test_chat_send_is_a_reaction_row_wired_in_the_boot_side_listener() -> None:
    """Item 19: measured before, `nmb.reacted` stayed unset after Enter and after a click on Send with the model off;
    after, both give `sent` (act nod, state reacting) 400 ms later. Wired in avatars.js: companion-menu.js loads lazily."""
    assert re.search(r'^  sent: \{ cool: 4000, ms: 1200, world: true, play: \["nod", "curious", 1200\] \},$', AV, re.M)
    assert 'event.key === "Enter" && !event.shiftKey && event.target?.id === "chat-input" && event.target.value.trim()' in AV
    assert 'event.target?.closest?.("#chat-send")' in AV and 'nameMarkBuddyReact("sent")' in AV


def test_a_lasting_toast_does_not_yield_to_settings_panes_buttons() -> None:
    """Item 24: measured before, the search-by-meaning question (944..1424 x 730..855) sat at opacity 0.12, inert, 12 s
    after Settings opened (and a minute in the blind run) because the pane's custom-theme-save met it."""
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert 'querySelectorAll("button:not(.panel-grip, #settings-modal *)")' in status
