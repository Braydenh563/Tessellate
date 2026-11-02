"""Audit 1029 rank 48 (G12, G21, X10): on the light theme the automatic
category colours are 1.0 to 2.7 against the map's ground (need 3 for a mark),
and the search placeholder was dimmed under its own token. A dot's rim is the
part of it that must clear 3:1, so on a light ground the rim is deeper; every
placeholder now takes `--muted` whole.

Measured with `/tmp/claude-0/graphb/c48b.js` (session scratch): the worst rim
of the 22 automatic colours was 1.87 at a quarter deeper and 3.37 at 45%, and 3.00 off the painted sprite, so it is half.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
FORMS = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: The automatic colours that fall under 3:1 as a plain disc on the light map
#: ground (247, 246, 244), measured; the rim must clear it for each of them.
LIGHT_DOTS = [
    "#dc8e42", "#7db0ac", "#dbbf5b", "#f4a8b0", "#b8b1ad", "#95cbc2", "#f7f7bb", "#c1bed6",
    "#ec8c81", "#89afca", "#ecb373", "#b0d176", "#f7d2e5", "#d9d9d9", "#b687b6", "#cfe7c9", "#efe17f",
]


def _fn(name: str) -> str:
    found = re.search(rf"^(?:async )?function {name}\(.*?^\}}", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _run(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@needs_node
def test_a_dot_on_a_light_ground_has_a_rim_that_clears_three_to_one() -> None:
    script = (
        "let gcTokens = { card: '#ffffff' };"
        + _fn("gcHexToRgb")
        + _fn("gcMixRgb")
        + _fn("gcRimShare")
        + f"""
        const lin = (v) => {{ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }};
        const L = (r, g, b) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
        const ground = [247, 246, 244];
        const ratio = (a, b) => (Math.max(L(...a), L(...b)) + 0.05) / (Math.min(L(...a), L(...b)) + 0.05);
        const worst = Math.min(...{json.dumps(LIGHT_DOTS)}.map((hex) => {{
          const rim = gcMixRgb(gcHexToRgb(hex), 0, gcRimShare()).match(/\\d+/g).map(Number);
          return ratio(rim, ground);
        }}));
        gcTokens = {{ card: '#1b1f2a' }};
        const dark = gcRimShare();
        gcTokens = {{ card: 'oklch(0.2 0 0)' }};
        console.log(JSON.stringify({{ worst, dark, odd: gcRimShare() }}));
        """
    )
    out = _run(script)
    assert out["worst"] >= 3.0
    assert out["dark"] == 0.25 and out["odd"] == 0.25  # dark grounds and unreadable tokens keep the quarter


def test_the_rim_is_drawn_with_the_ground_aware_share() -> None:
    assert "gcMixRgb(rgb, 0, gcRimShare())" in _fn("gcPaintCore")


def test_a_placeholder_is_the_muted_token_whole() -> None:
    rule = re.search(r"::placeholder \{(.*?)\}", FORMS, re.S).group(1)
    assert "color: var(--muted)" in rule
    assert "opacity: 1;" in rule, "a dimmed --muted is 3.68:1 on the dock search field"
