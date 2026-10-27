"""Atlas standing on the status bar does not hit the bar's buttons (brief
2026-10-27). Measured (scratchpad/ui-sweeps/atlasbarhit.js, 1280x720): the bar
is at 683.2 and its buttons start 4.9px under it; the tail, drawn 6px under
the soles standing, made 19 of 31 stands along the bar "hit". The tail now
stops at the soles standing; `nameMarkBuddyHits` runs here in node as
written, against the bar's buttons from that sweep."""

from __future__ import annotations

import json
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


#: The status bar's buttons at 1280x720 (its top at 683.2), from the sweep.
BAR = "[[47,688.1,75,716],[83,688.1,168,716],[1009,688.1,1041,716],[1237,688.1,1265,716]]"


def _hits(calls: str):
    script = "\n".join(
        [
            "const NMB_W = 64, NMB_H = 92, NMB_HEAD = 52, NMB_SEAT = 72, NMB_FEET = 90, NMB_GRIP = 5, NMB_DROP = 12;",
            "const nmb = { scale: 1 };",
            "const document = { querySelector: () => ({}) };",
            f"const OBS = {BAR}.map(([left, top, right, bottom]) => ({{ left, top, right, bottom }}));",
            *[_fn(n) for n in ("nameMarkBuddyOrigin", "nameMarkBuddyScaled", "nameMarkBuddyShape", "nameMarkBuddyShapeAt1", "nameMarkBuddyHits")],
            f"console.log(JSON.stringify({calls}));",
        ]
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_standing_on_the_bar_over_its_buttons_is_clear():
    # Atlas's soles on the bar's top (683.2), over each button and between.
    got = _hits("[0, 40, 60, 100, 1000, 1220].map((x) => nameMarkBuddyHits(x, 683.2 - NMB_FEET, 'stand', OBS, ''))")
    assert got == [False] * 6


@needs_node
def test_a_stand_sunk_into_the_buttons_still_hits():
    # 12px lower, its body is over the buttons: the test still sees them.
    got = _hits("[nameMarkBuddyHits(60, 683.2 - NMB_FEET + 12, 'stand', OBS, ''), nameMarkBuddyHits(1000, 683.2 - NMB_FEET + 12, 'float', OBS, '')]")
    assert got == [True, True]
