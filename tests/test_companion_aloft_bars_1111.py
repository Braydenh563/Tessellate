"""INBOX 1111: a glide to a new perch no longer draws the companion over the top bar (390 wide).

Reproduced at 390x844 on the Notes list (Atlas perched on a card, the list scrolled 300px): the shutter had the
figure cut under the bar at rest, the move to a new perch lifted every clip (`nameMarkBuddyAloft`, INBOX 1463) and the
glide began from where the figure was: 15 rows of its tail drawn over the bar (pixel diff of the bar's strip,
companion hidden vs shown, 12 of 12 paused steps of the first 264ms of the glide; 2 to 3 of 3 scrolls). The lift now
clips the band at the bars' edges when the move is between two perches in a panel (`cut`); an entrance, a move from or
to a bar, and a flight stay whole.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _node(script: str):
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


CUT = re.search(r"^nameMarkBuddyAloft\.cut = .*;$", AV, re.M).group(0)


@needs_node
def test_the_cut_is_the_bars_edges_in_the_bands_own_px() -> None:
    # The measured band at 390x844: top 110, 668 tall; the top bar's bottom edge at 57.78 (58 whole), the phone's dock at 800.
    out = _node(
        "const nameMarkBuddyAloft = {};\n"
        + CUT
        + "\nprocess.stdout.write(JSON.stringify(nameMarkBuddyAloft.cut({ barLo: 58, barHi: 800, top: 110, height: 668 })));"
    )
    assert out == "inset(-52px -9999px -22px -9999px)", "from the bar's bottom (52px above the band's top) to the dock's top (22px under its bottom)"


@needs_node
def test_a_move_between_two_perches_keeps_the_lift_but_clips_at_the_bars_and_landing_clears_both() -> None:
    script = (
        "const nameMarkBuddyAloft_cut = " + CUT.split("= ", 1)[1].rstrip(";") + ";\n"
        + _fn("nameMarkBuddyAloft").replace("nameMarkBuddyAloft.cut", "nameMarkBuddyAloft_cut")
        + r"""
const mk = () => ({ style: { overflow: "", clipPath: "" } });
const run = (cut) => {
  const band = mk();
  band.firstElementChild = mk();
  const listeners = {};
  const anim = { playState: "running", addEventListener: (k, f) => { listeners[k] = f; } };
  globalThis.document = { getElementById: () => band };
  // Off a bar perch the rest clip is none (tests/test_companion_rest_bars_1111.py), so landing leaves the band unclipped.
  nameMarkBuddyAloft.rest = () => { band.style.clipPath = ""; };
  globalThis.nmb = { anim, ride: { barLo: 58, barHi: 800, top: 110, height: 668 } };
  nameMarkBuddyAloft(cut);
  const aloft = { overflow: band.style.overflow, shutter: band.firstElementChild.style.overflow, clip: band.style.clipPath };
  listeners.finish();
  return { aloft, landed: { overflow: band.style.overflow, shutter: band.firstElementChild.style.overflow, clip: band.style.clipPath } };
};
process.stdout.write(JSON.stringify({ cut: run(true), whole: run(false) }));
"""
    )
    out = _node(script)
    assert out["cut"]["aloft"] == {"overflow": "visible", "shutter": "visible", "clip": "inset(-52px -9999px -22px -9999px)"}
    assert out["cut"]["landed"] == {"overflow": "", "shutter": "", "clip": ""}, "landing puts the ride's own clip back and drops the cut"
    assert out["whole"]["aloft"]["clip"] == "" and out["whole"]["aloft"]["overflow"] == "visible", "an entrance stays whole in the air (INBOX 1463)"


def test_only_a_move_between_perches_in_a_panel_asks_for_the_cut() -> None:
    move = _fn("nameMarkBuddyMoveTo")
    assert "const fromKind = nmb.perch;" in move, "where it came from is read before the move sets its own perch"
    assert 'const overBars = ["bar", "hang", "dock", "corner", "pinned"];' in move
    assert "nameMarkBuddyAloft(!overBars.includes(spot.kind) && !overBars.includes(fromKind));" in move
    assert move.index("const fromKind = nmb.perch;") < move.index("nmb.perch = spot.kind"), "before it is overwritten"
    appear = _fn("nameMarkBuddyAppear")
    assert "nameMarkBuddyAloft();" in appear, "the entrance from above the window is drawn whole (tests/test_companion_fall_split_1463.py)"


def test_the_bars_edges_are_whole_pixels_and_follow_the_band() -> None:
    ride = _fn("nameMarkBuddyRideBox")
    # A cut on 57.78 left a row of the figure over the bar's last pixel (measured: 1 to 74 px a step).
    assert "r.barLo = bars.top ? Math.ceil(bars.top.bottom) : 0;" in ride
    assert "r.barHi = bars.bottom ? Math.floor(bars.bottom.top) : innerHeight;" in ride
    assert "if (band.style.clipPath) band.style.clipPath = nameMarkBuddyAloft.cut(r);" in ride, "a band that moves in the air keeps its cut on the bars"
