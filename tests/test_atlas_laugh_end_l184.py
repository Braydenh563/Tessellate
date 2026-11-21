"""L184: laughing's end hands back with "What it does" set to off too.

Left from 2026-10-05 (atlas-1005.md): laughing's end moved the whole figure about 3 px in a frame. Measured
2026-11-21 in real time (`blendprobe.js`, port 8803, 1440 wide, feminine, every animation frame, the figure box,
body and head layers and lower body): with "What it does" at fewer the end is eased (0.59 px at most in a frame,
against 1.93 while the giggle ran); with it off the giggle still runs (its gate is motion, not actions) but the
hand-over skipped, because it asked `nameMarkIdleQuiet`, which also counts actions off: 3.21 px in one frame.
The hand-over now asks only whether motion is still (`nameMarkMotionStill`).
"""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

AV = unwrapped((Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    assert f"function {name}(" in AV, f"{name} is gone"
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def test_the_hand_over_asks_motion_not_actions() -> None:
    blend = _fn("nameMarkBuddyBlend")
    assert "nameMarkMotionStill()" in blend
    assert "nameMarkIdleQuiet()" not in blend, "actions off still runs the giggle, so its end must be eased"


def test_still_motion_is_the_motion_half_of_idle_quiet() -> None:
    still = _fn("nameMarkMotionStill")
    assert 'root.dataset.avatarMotion === "off"' in still and "reducedMotionWanted()" in still
    assert "nameMarkBuddyActions" not in still
    quiet = _fn("nameMarkIdleQuiet")
    assert "nameMarkMotionStill()" in quiet and 'nameMarkBuddyActions() === "off"' in quiet
