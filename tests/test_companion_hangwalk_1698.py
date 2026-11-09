"""INBOX 1698: the in-app companion, hanging from the top bar and sent along it, swung its walking legs while it slid
across the top ("flew across the top of my screen but with the walking legs"). A body hanging by its hands has no
stride: `nmb.feetDown` is true only for a body that set off from its feet, and every site that adds the walk's
class (the walk, the portal and edge walks) asks it."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
TRAVEL = (ROOT / "frontend" / "js" / "companion-travel.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def feet_down() -> str:
    start = AV.index("nmb.feetDown = ")
    return AV[start : AV.index("\n", start)]


@needs_node
@pytest.mark.parametrize(("was", "feet"), [("hang", False), ("stand", True), ("sit", True), ("", True)])
def test_only_a_body_set_off_from_its_feet_walks(was: str, feet: bool) -> None:
    script = f"const nmb = {{ poseWas: {json.dumps(was)} }};\n{feet_down()}\nconsole.log(JSON.stringify(nmb.feetDown()));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) is feet


def test_every_walk_start_asks_it() -> None:
    # the class is added only behind the check, in the walk (avatars.js) and the travel steps (companion-travel.js)
    assert re.search(r"if \(nmb\.feetDown\(\)\) nameMarkBuddyBlend\(buddy, \(\) => buddy\.classList\.add\(\"nmb-walking\"\)", AV)
    assert 'nmb.feetDown() && !(arrive && nmb.pose === "hang")' in TRAVEL
    # both ways in (the portal's and the edge walk's second half) are marked as arrivals
    assert "T * 0.29, true)" in TRAVEL and "lead + t1 + gap, t2, true)" in TRAVEL
