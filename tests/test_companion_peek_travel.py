"""A companion on its way to a peek is whole; it tucks in when it arrives.

INBOX 1300 C01, the owner: "If I throw the companion or atlas across the
screen and it lands on a ui element but then it decides to fall through to
peep over the bottom bar, it does the peak animation first so it gets cut
in half and then falls like that to the bottom bar."

`nameMarkBuddyLegsNow` runs here in node as written; the move in a browser
is `scratchpad/ui-sweeps/peektravel.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_peek_waits_for_arrival():
    js = _fn("nameMarkBuddyLegsNow") + (
        "console.log(JSON.stringify(["
        "nameMarkBuddyLegsNow({legs:'peek'}, true),"
        "nameMarkBuddyLegsNow({legs:'peek'}, false),"
        "nameMarkBuddyLegsNow({legs:''}, true),"
        "nameMarkBuddyLegsNow({}, false)]));"
    )
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["", "peek", "", ""]


def test_move_tucks_in_after_the_way():
    body = _fn("nameMarkBuddyMoveTo")
    assert "buddy.dataset.legs = nameMarkBuddyLegsNow(spot, travels)" in body
    assert 'buddy.dataset.legs = spot.legs || "";' not in body.split("nmb.legsTimer = setTimeout")[0]
    # The tuck is armed after the way is chosen, at the end of its animation,
    # and only for the spot it was armed for.
    after = body.split("nameMarkBuddyGo(buddy, dx, dy")[1]
    assert "nmb.legsTimer = setTimeout" in after
    assert "getComputedTiming" in after
    assert "nmb.spot === spot" in after
    assert body.index("clearTimeout(nmb.legsTimer)") < body.index("nameMarkBuddyLegsNow(")
