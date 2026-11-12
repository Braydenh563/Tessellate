"""The rig's list of running arm animations is seeded at its first look, not when it attaches (INBOX 1741).

The owner's log: `frame 227ms on dashboard: atlas-motion.js after 13ms`. `getAnimations()` settles the page's
style first, and the attach ran inside the timer that dressed a figure (`atlas.js step`), with the figure
just appended: 17ms of that task at 4x CPU, one flush for the whole dirty page, for each figure. The first
look is taken after a frame has drawn (`atlasRigWake.afterPaint`), where the list is read from a clean style.
The set is kept by the probe's events in between, so what it holds is the same.
"""

from __future__ import annotations

import re
from pathlib import Path

MOTION = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", MOTION, re.S | re.M)
    assert match, name
    return match.group(0)


def test_attaching_does_not_scan_the_probe() -> None:
    assert "getAnimations" not in _fn("atlasRigAttach")
    assert "getAnimations" not in _fn("atlasProbeWatch")


def test_the_first_look_seeds_the_set_once() -> None:
    seed = MOTION[MOTION.index("atlasProbeWatch.seed = (arm) => {") :][:260]
    assert "arm.probe.getAnimations()" in seed and "arm.running.add(a.animationName)" in seed
    frame = _fn("atlasRigFrame")
    assert "getAnimations" not in frame, "the frame itself never scans"
    look = MOTION[MOTION.index("atlasRigWake.look = function atlasRigLook") : MOTION.index("atlasRigWake.look.soon =")]
    call = look.index("atlasProbeWatch.seed(arm)")
    assert "if (!rig.reads)" in look[call - 80 : call], "only before anything has been read"
    assert call < look.index("atlasRigRead("), "and before the first read uses the set"
