"""INBOX 1111: a companion at rest on a bar perch draws nothing inside the bar.

Pixel diff of the bar's strip, companion hidden vs shown (the method of tests/test_companion_cut_head_1598.py), Atlas at
rest at 360 to 2560 wide and 100 to 200% zoom: hanging from the top bar, its ring, head and wisps reached 10 to 18px up into
it (27 at 390 wide, 150%) and drew over the lower edge of the "Reminders" tab at 1280; sitting, standing or tucked on the dock
or status bar, its tail and legs reached 19 to 24px down into it. The band has no box off a ride, so `nameMarkBuddyAloft.rest`
gives it an inset clip that starts at the top bar's lower edge (hanging) or ends at the bottom bar's upper one, in whole px.
A pull or a throw lifts it, a glide in the air keeps its own rule (tests/test_companion_aloft_bars_1111.py).
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
THROW = unwrapped((ROOT / "frontend" / "js" / "companion-throw.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


REST = re.search(r"^nameMarkBuddyAloft\.rest = \(on = true\) => \{.*?^\};$", AV, re.M | re.S).group(0)


def _clip(perch: str, *, top=None, bottom=None, ride=False, on=True) -> str:
    script = (
        "const nameMarkBuddyAloft = {};\n"
        f"const nmb = {{ perch: {json.dumps(perch)}, ride: {json.dumps(ride)} }};\n"
        "const band = { style: { clipPath: 'stale' } };\n"
        "globalThis.document = { getElementById: () => band };\n"
        "globalThis.innerWidth = 1280;\nglobalThis.innerHeight = 800;\n"
        f"const nameMarkBuddyLedges = () => ({{ top: {json.dumps(top)}, bottom: {json.dumps(bottom)} }});\n"
        + REST
        + f"\nnameMarkBuddyAloft.rest({'true' if on else 'false'});\nprocess.stdout.write(JSON.stringify(band.style.clipPath));"
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_hanging_keeps_only_what_is_under_the_top_bars_edge_in_whole_px() -> None:
    # 390 wide at 150%: the top bar's lower edge is at 57.78 css px; a cut on the fraction left a row of ring over the bar.
    assert _clip("hang", top={"bottom": 57.78}, bottom={"top": 800}) == "inset(58px -9999px -9999px -9999px)"


@needs_node
def test_a_bar_perch_keeps_only_what_is_over_the_bottom_bars_edge_in_whole_px() -> None:
    # The band is 0 by 0 at the window's corner, so a bottom inset of minus 756 is a clip line 756px down.
    assert _clip("bar", top={"bottom": 44}, bottom={"top": 756.4}) == "inset(-9999px -9999px -756px -9999px)"


@needs_node
def test_nothing_is_clipped_on_other_perches_on_a_ride_or_while_lifted() -> None:
    bars = {"top": {"bottom": 44}, "bottom": {"top": 756}}
    assert _clip("card", **bars) == "", "a card or a tab stands off the bars; its own shutter handles a scroll"
    assert _clip("dock", **bars) == ""
    assert _clip("hang", ride=True, **bars) == "", "on a ride the band is the panel's box and has its own clip"
    assert _clip("hang", on=False, **bars) == "" and _clip("bar", on=False, **bars) == "", "carried or thrown, it is whole"
    assert _clip("hang", top=None, bottom={"top": 756}) == "", "no top bar on the page, nothing to keep off"
    assert _clip("bar", top={"bottom": 44}, bottom=None) == ""


def test_the_clip_follows_the_figure_to_rest_and_lifts_with_a_pull_or_a_throw() -> None:
    state = _fn("nameMarkBuddyState")
    assert 'if (!nmb.flight && !buddy.classList.contains("nm-buddy-dragging") && nmb.anim?.playState !== "running") nameMarkBuddyAloft.rest();' in state
    move = _fn("nameMarkBuddyMoveTo")
    assert move.index("nameMarkBuddyAloft.rest();") < move.index("nameMarkBuddyAloft(!overBars"), "put first (an instant move, or one of under a px, returns early), lifted after if it travels"
    assert move.index("nmb.perch = spot.kind") < move.index("nameMarkBuddyAloft.rest();"), "for the perch it is put on, not the one it left"
    aloft = _fn("nameMarkBuddyAloft")
    assert "if (on) nameMarkBuddyAloft.rest();" in aloft, "landing from a glide puts the rest clip back (it used to clear the clip)"
    assert "else band.style.clipPath = cut && nmb.ride ? nameMarkBuddyAloft.cut(nmb.ride) : \"\";" in aloft
    assert "nameMarkBuddyRide(null);\n      nameMarkBuddyAloft.rest(false);" in AV, "a pull lifts it before it is carried"
    assert 'buddy.classList.add("nm-buddy-dragging");\n  nameMarkBuddyAloft.rest(false);' in THROW, "and so does a throw"
