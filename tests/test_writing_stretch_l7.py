"""A long writing run that ends is a stretch, on both companions (L-chat-7, Brief 88 N9).

Brief 88 N9 asked for a stretch when a long writing run ends; what shipped was
`typing_burst`, a nod after 30 s. A run of a minute or more is now
`writing_stretch` (the in-app `stretch` act, the desk's `dusk_stretch`
pose); 30 s to a minute stays the nod. Fixed clocks, no real time.
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
MENU = unwrapped((ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const [block] = process.argv.slice(1);
const nmb = {};
eval(block);
const s = nmb.dayLife;
const run = (secs) => {
  s.run = null;
  let t = new Date(2026, 10, 9, 14).getTime();
  for (let i = 0; i * 900 < secs * 1000; i++) { s.input(new Date(t), true); t += 900; }
  return s.rested(t + 5000);
};
console.log(JSON.stringify({ short: run(8), nod: run(40), stretch: run(75) }));
"""


@needs_node
def test_the_app_side_stretches_after_a_minute():
    block = re.search(r"^nmb\.dayLife = \{.*?\n\};$", MENU, re.S | re.M).group(0)
    got = json.loads(subprocess.run(["node", "-e", HARNESS, block], capture_output=True, text=True, timeout=60, check=True).stdout)
    assert got == {"short": [], "nod": ["typing_burst"], "stretch": ["writing_stretch"]}


def test_the_app_row_plays_a_stretch():
    row = re.search(r"^\s+writing_stretch: \{(.*)\},$", MENU, re.M)
    assert row and '"stretch"' in row.group(1) and "world: true" in row.group(1)


def test_the_desk_side_stretches_after_a_minute():
    from tessellate.core.overlay import extras
    from tessellate.core.overlay import screenwatch as sw

    def run(secs: float) -> list[str]:
        w = sw.ScreenWatch(downloads=lambda: None)
        t = 0.0
        while t < secs:
            w.typing_seen(t, True)
            t += 2.0
        return w.typing_seen(t + 5.0, False)

    assert run(8) == [] and run(40) == ["typing_burst"] and run(76) == ["writing_stretch"]
    assert "stretch" in extras.REACTIONS["writing_stretch"].act
