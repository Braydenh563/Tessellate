"""Between two states, a beat, never the same twice running (INBOX 1463).

The owner, 2026-10-31: "I want every micro detail animated and accounted for
and for it to be a non intrusive companion". Each change of state with a body
to it gets a small move added to the pose (arriving, coming to, done
reacting), picked from two so it is not the same twice running; with less
motion asked for there is none. On a new page it glances at the page rather
than crossing it.
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


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _block(name: str) -> str:
    start = AV.index(f"const {name} = ")
    return AV[start : AV.index("\n};\n", start) + 3]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_each_change_with_a_body_gets_its_beat_and_never_the_same_twice() -> None:
    script = "\n".join([
        _block("NMB_SETTLES"),
        re.search(r"^const NMB_BEAT_MS = .*;$", AV, re.M).group(0),
        "let nmb = {}; let still = false; const played = [];",
        "function nameMarkBuddyStill() { return still; }",
        _fn("nameMarkBuddyPickVariant"),
        _fn("nameMarkBuddySettleKind"),
        _fn("nameMarkBuddySettleIn"),
        "const char = { animate: (frames, o) => played.push([frames.length, o.duration, o.composite]) };",
        "const buddy = { dataset: { turn: 'r' }, querySelector: () => char };",
        "const kinds = [['moving','resting'],['moving','idling'],['sleeping','resting'],['reacting','resting'],['resting','moving'],['idling','sleeping'],['resting','idling']].map(([a,b]) => nameMarkBuddySettleKind(a,b));",
        "const picks = []; for (let i = 0; i < 12; i++) { nameMarkBuddySettleIn(buddy, 'moving', 'resting'); picks.push(nmb.settleLast.arrive); }",
        "still = true; const before = played.length; nameMarkBuddySettleIn(buddy, 'moving', 'resting');",
        "console.log(JSON.stringify({ kinds, picks, composite: played[0][2], stillPlayed: played.length - before }));",
    ])
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert got["kinds"] == ["arrive", "arrive", "wake", "calm", "", "", ""]
    assert all(a != b for a, b in zip(got["picks"], got["picks"][1:])), got["picks"]
    assert got["composite"] == "add" and got["stillPlayed"] == 0


def test_the_beats_are_small() -> None:
    # A beat is a give, not a move: under 2px and 2 degrees, under a second.
    for ways in re.findall(r"\[\[0, 0, 0\].*?\]\]", _block("NMB_SETTLES")):
        for _, y, r in json.loads(ways):
            assert abs(y) <= 2 and abs(r) <= 2, ways
    ms = [int(n) for n in re.findall(r"\d+", re.search(r"^const NMB_BEAT_MS = (.*);$", AV, re.M).group(1))]
    assert max(ms) < 1000


def test_on_a_new_page_it_glances_at_the_page() -> None:
    glance = _fn("nameMarkBuddyGlanceAtPage")
    assert "nameMarkBuddyStill()" in glance and "nameMarkBuddyAim([innerWidth / 2, innerHeight * 0.45])" in glance
    assert "setTimeout(nameMarkBuddyRelease, 1300)" in glance
    assert "setTimeout(nameMarkBuddyGlanceAtPage, NMB_QUIET_FADE_MS + 120);" in _fn("nameMarkBuddyQuietEnter")
    assert "if (fresh) nameMarkBuddyGlanceAtPage();" in _fn("nameMarkBuddyBeat")
