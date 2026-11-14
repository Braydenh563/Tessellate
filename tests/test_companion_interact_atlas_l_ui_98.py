"""The Atlas interact sweep's eyes-off and toss checks (L-ui-modernisation-98).

KIND=atlas companioninteract.js failed 2 runs in 5, and both causes were the
app's:

- Eyes off: Atlas's own glances (atlas-micro.js) aimed at the pointer with
  Faces follow the pointer off, 40% of glances and every "back" step.
- Toss: Atlas's tail box reached its soles, the status bar's buttons start
  3.9px under them (measured, 868.09 against 864.2 at 1440x900) and the hit
  test pads 4px, so it could stand nowhere over the bar's right-hand buttons
  and a toss to the right came down on the seat at x 804, 247 to 323px off.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MICRO = (ROOT / "frontend" / "js" / "atlas-micro.js").read_text(encoding="utf-8")
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
SWEEP = (ROOT / "scratchpad" / "ui-sweeps" / "companioninteract.js").read_text(encoding="utf-8")


def test_atlas_micro_looks_take_the_pointer_only_while_faces_follow_it():
    """Source text: every pointer a micro look aims at comes from atlasMicroDo.pointer, which is null with avatarFollow off."""
    assert 'atlasMicroDo.pointer = () => (document.documentElement.dataset.avatarFollow === "off" ? null : nmb.pointer);' in MICRO
    body = MICRO[MICRO.index("atlasMicroDo.glance = function"):]
    assert not re.search(r"nameMarkBuddyAim\(nmb\.pointer", body)
    assert "point = nmb.pointer" not in body and "const p = nmb.pointer;" not in body
    assert "pointer: !!atlasMicroDo.pointer()" in MICRO


def test_a_standing_atlas_tail_stops_short_of_the_floor_by_the_hit_gap():
    """Source text: standing, the tail's box ends the hit test's 4px gap above its soles, so the floor's own buttons are not hit."""
    assert "bottom: y + drop + NMB_FEET + (pose === \"stand\" ? -4 : 4) }" in AV


def test_the_sweep_excuses_only_a_micro_look_away_from_the_pointer():
    """Source text: with the setting off, eyes on at the check count against it unless a micro look away from the pointer ran."""
    assert "window.__microLooks" in SWEEP
    assert "off.push(await page.evaluate" in SWEEP
    assert "fails.push(`eyes with the setting off: ${JSON.stringify(off)}`)" in SWEEP


def test_the_sweep_tosses_with_its_own_times_once_the_throw_has_loaded():
    """Source text: the toss waits for the lazy throw file and sends its moves and let-go with CDP timestamps 12ms apart."""
    assert "await page.evaluate(() => ensureModule('companionThrow'));" in SWEEP
    assert "timestamp: t0 + i * 0.012" in SWEEP and "timestamp: t0 + 0.076" in SWEEP
