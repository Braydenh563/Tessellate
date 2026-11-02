"""The companion is drawn whole while it moves (INBOX 1463, 1432).

The owner, 2026-10-30: "the companion just fell down from the library roof but
at like 3 spots along the way it looked like it went behind parts of the
elements and got cut in half for a split second"; 2026-10-31: "the slow fall of
the companion where it got like cut in half at like 3 points as it fell just
happened again".

Measured cause (a per-frame hit test of the figure with every animation stepped
16ms at a time, the companion-1031 fall probe): riding a panel's scroll, the
companion is drawn in a band clipped to that panel's visible box, below its
sticky bar (`nameMarkBuddyRideBox`, `.nmb-riding { overflow: clip }`). The clip
is right at rest and wrong in the air: `nameMarkBuddyMoveTo` re-glues it to the
destination's panel before the move plays, so a drop from the Library's
sub-tabs onto a card was clipped at the card list's top edge (y 106) for the
first 528ms of the fall, 34 of 69 frames, every one of the 138 sampled rows
hidden at the start; and the fall entrance from above the window was cut at
the top bar's edge in 30 of 139 frames. With the clip lifted while a move
plays: 0 frames.

Not the other causes the brief named: the host moves by `transform` and the
`translate` animation (no top/left), and headless frame captures at 1x and
1.25x showed no seam inside the figure. A GPU seam between Atlas's 38
composited layers on the owner's Windows webview is not verified here.
"""

from __future__ import annotations

import re

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = AV.index(f"function {name}(")
    end = AV.index("\n}\n", start)
    return AV[start:end]


def test_a_move_lifts_the_ride_clip_and_landing_puts_it_back():
    body = _body("nameMarkBuddyAloft")
    # The band and its shutter both clip while riding; both are lifted.
    assert "band.firstElementChild" in body
    assert '"visible"' in body
    # Only while a move plays, and put back when that move ends either way.
    assert 'playState !== "running"' in body
    assert '"finish"' in body and '"cancel"' in body


def test_every_move_and_every_entrance_is_drawn_aloft():
    move = _body("nameMarkBuddyMoveTo")
    go = move.index("nameMarkBuddyGo(buddy, dx, dy, spot, poseChanged, was, underway);")
    assert "nameMarkBuddyAloft()" in move[go:], "a move re-glues to the destination's band before it plays"
    arrive = _body("nameMarkBuddyArrive")
    assert re.search(r"nmb\.enteredBy = nameMarkBuddyEnter\(buddy, spot\);\s*nameMarkBuddyAloft\(\);", arrive)


def test_a_landing_restores_the_clip_only_when_no_newer_move_is_flying():
    body = _body("nameMarkBuddyAloft")
    # A move cut short by the next reports its cancel after the next began:
    # the clip stays lifted for the new one.
    assert "nmb.anim === anim" in body or "nmb.anim !== anim" in body
