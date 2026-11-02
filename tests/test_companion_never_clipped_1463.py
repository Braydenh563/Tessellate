"""The companion never passes through a bar and no move clips it (INBOX 1463).

The owner, 2026-10-31 15:25: "the companion just went through the bottom bar
and started falling from the top bar and along the way it was like part of its
body was missing" (screenshot: Questions, the companion on the status bar, its
head and upper body cut by a straight line).

Cause, measured (scratchpad probe, 1440x900, every frame of every far move on
Notes' sub-tabs, Library and Graph): the `duck` move of
`companion-travel.js` hid it behind one bar with an animated `clip-path` and
let it down from behind the other, so it left through the bottom edge, was
drawn below the status bar's top line and came back in from the top, cut by an
inset that was not the bar's line for most of the way. No other move touched
a clip. The move is gone; the class (a move out by the top or bottom, a
clip-path from a move) is pinned here as text, the per-frame count by the
sweep named in the CHANGELOG line.
"""

from __future__ import annotations

import re

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
TRAVEL = (JS / "companion-travel.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")
CODE = "\n".join(line for line in TRAVEL.splitlines() if not line.lstrip().startswith("//"))


def test_no_move_clips_the_companion() -> None:
    assert "clipPath" not in CODE and "clip-path" not in CODE
    assert "clip-path" not in CSS


def test_there_is_no_duck_and_no_bar_to_go_behind() -> None:
    assert "duck" not in CODE
    assert "nameMarkBuddyLedges" not in CODE
    assert "COMPANION_TRAVEL_MOVES = [" in CODE
    moves = re.search(r"COMPANION_TRAVEL_MOVES = \[([^\]]*)\]", CODE).group(1)
    assert "duck" not in moves


def test_no_move_leaves_the_window_by_the_top_or_bottom() -> None:
    # Every player's frames move it along x (edge) or in place (smoke, portal); a vertical exit
    # would need a translate with a y built from the window's height.
    assert "translate: `${" in CODE and not re.search(r"translate: `[^`]*(innerHeight|bottom|top)", CODE)
    assert "outY" not in CODE and "inY" not in CODE
