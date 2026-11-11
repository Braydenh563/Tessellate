"""INBOX 1598: a head the shutter has cut is not over what is under the cut, so the look does not set it down whole.

The owner: "I scrolled down and up on the ask subtab and the companion got carried to be cut off and floating at the
top of the screen". Reproduced at 1366x768 (a pixel diff of the top bar with the companion hidden and shown,
scratchpad `askscroll.js`): perched on a matching-records card in the Ask sub-tab, scrolled down until the card was
out of sight and back up. The card came into view under the sticky sub-tab strip with the head behind the bars
(the shutter had it cut at y=96). A moment after the scroll stopped, `nameMarkBuddyCheck` counted the top bar's tabs
as covered by the figure's whole drawn box, stepped it aside, and the move placed it again with a band widened to
the head: Atlas stood whole at y=2, 44px of it over the top bar, over "Library" and its neighbours.
The look now skips controls wholly above the clip line (the band's top, brought down by the shutter at this scroll).
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _shut(ride: dict, scrolls: list[float]) -> list[float]:
    """The shutter's edge, as `nameMarkBuddyCheck` computes it, at each scroll offset."""
    script = (
        "const NMB_RIDE_PX = 1e6;\n"
        + _fn("nameMarkBuddyRideFrames")
        + """
const r = %s;
console.log(JSON.stringify(%s.map((u) => nameMarkBuddyRideFrames(r.s0, r.up, r.down, r.upSpan, r.downSpan).shut(u))));
"""
        % (json.dumps(ride), json.dumps(scrolls))
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_clip_line_is_where_the_shutter_has_brought_the_band_by_this_scroll() -> None:
    # The measured ride at 1366x768 on a record card: band top 54, sticky strip ending at 96 (up 42), perched at 544.
    ride = {"s0": 544, "up": 42, "down": 0, "upSpan": 58, "downSpan": 561}
    at, closed, past, other = _shut(ride, [544, 565, 606, 400])
    assert at == 0, "where it was perched nothing is cut"
    assert closed == pytest.approx(21, abs=0.01), "the clip line comes down a px per px scrolled"
    assert past == 42, "and stops at the sticky strip's edge"
    assert other == 0, "scrolled the other way nothing is cut from the top"


def test_the_look_for_a_covered_control_leaves_out_what_the_clip_line_has_cut() -> None:
    check = _fn("nameMarkBuddyCheck")
    assert "nameMarkBuddyRideFrames(ride.s0, ride.up, ride.down, ride.upSpan, ride.downSpan).shut(ride.el.scrollTop)" in check
    assert "ride.top + Math.max(0, " in check, "the clip line is the band's top, brought down"
    assert "boxes.filter((box) => box.bottom + 4 > cut)" in check, "a control wholly above it is not covered by what is drawn"
    # Both lists the look uses (the ones near its shape, then every one on the tab) go through it.
    assert check.count("yours(") == 2 and "const yours = (boxes) => seen(" in check
