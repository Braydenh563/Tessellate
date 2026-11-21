"""INBOX 1607 (a, c), the owner, of the masculine Atlas: "the eyes look creepy
especially when juggling stars" and "the shoulder to arm join should be
smoother". Measured first (a throwaway sweep, CHANGELOG 1607, 13
poses and 8 forced arm angles at 4x):

- the shoulder: his torso's corner stood out past a raised arm (70 to 130
  degrees) as a step, so the arm read as growing from the neck: up to 9
  outline points of the left arm crossed lit torso, and the closing of the
  paint added up to 0.5 px. Now the flank turns round each pivot on a circle
  of 2.2 and the arm starts on the pivot 4.4 across, so its root corners sit
  on that circle at any turn and its sides leave it on the tangent.
- the juggle: the pupils went up 1.6, so the ink's top met the white's top, a
  roll to the whites. His stops at 0.7; hers is unchanged.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_atlas_masc_1607 import _arms, _inside, _look, _path, _sample, _width_at

ROOT = Path(__file__).resolve().parent.parent
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")

R = 2.2
PIVOTS = {"l": (25.6, 41.0), "r": (36.4, 41.0)}
# Every arm angle an act or a mood sets on him (08-consistency.css), both ways.
ANGLES = (0, 10, 13, 16, 22, 24, 26, 28, 34, 40, 70, 100, 120, 130, 150, 163)


def test_the_pivots_are_the_css_transform_origins():
    for side, (x, y) in PIVOTS.items():
        assert f".nmb-arm-{side} {{ transform-origin: {x:g}px {y:g}px; }}" in CSS


def test_the_shoulder_is_a_ball_about_each_pivot():
    torso = _sample(_path("masculine", "torso"))[0]
    for side, (px, py) in PIVOTS.items():
        # Nothing comes nearer than the ball, and the outline runs on it for
        # T1 to T2, about 50 degrees (1.9 of outline, 40 samples a curve).
        dists = [math.dist(p, (px, py)) for p in torso]
        assert min(dists) >= R - 0.05, (side, min(dists))
        assert sum(abs(d - R) <= 0.05 for d in dists) >= 40, side


def test_the_ball_is_inside_the_torso_so_a_turned_root_never_shows():
    torso = _sample(_path("masculine", "torso"))
    for px, py in PIVOTS.values():
        for k in range(72):
            a = math.radians(k * 5)
            assert _inside(torso, px + (R - 0.08) * math.cos(a), py + (R - 0.08) * math.sin(a)), k * 5


def test_each_arm_starts_on_its_pivot_as_wide_as_the_ball():
    arms = _arms("masculine")
    for side, (px, py) in PIVOTS.items():
        assert arms[side][0][:2] == [px, py], side
    w0, _ = json.loads(re.search(r"armWidth: (\[[^\]]+\])", _look("masculine")).group(1))
    assert w0 / 2 == R
    # So the root's corners lie on the circle at every angle the acts turn it.
    for side, (px, py) in PIVOTS.items():
        s = arms[side][0]
        dx, dy = s[2] - s[0], s[3] - s[1]
        n = math.hypot(dx, dy)
        for deg in ANGLES:
            for sgn in (1, -1):
                a = math.radians(sgn * deg)
                ux, uy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
                corner = (px - uy / n * R, py + ux / n * R)
                assert abs(math.dist(corner, (px, py)) - R) < 1e-9


def test_the_proportions_hold_with_the_ball():
    torso = _path("masculine", "torso")
    assert 14.4 <= _width_at(torso, 40) <= 14.9
    waist = min(_width_at(torso, y / 10) for y in range(440, 560))
    assert _width_at(torso, 40) / waist >= 1.5


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_torso_edge_keeps_both_flanks_whatever_their_curve_count():
    start = ATLAS.index("function atlasTorsoEdge(d)")
    fn = ATLAS[start : ATLAS.index("\n}\n", start) + 2]
    script = fn + "\nconsole.log(JSON.stringify([%s, %s].map(atlasTorsoEdge)));" % (
        json.dumps(_path("masculine", "torso")),
        json.dumps(_path("feminine", "torso")),
    )
    his, hers = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # Seven curves for him (two flanks of three, the hem), five for her: the hem goes.
    assert his.count("C") == 6 and "C28 63.4 34 63.4 36 61" not in his and his.count("M") == 2
    assert hers.count("C") == 4 and hers.count("M") == 2
    assert "M36 61C35.2 55.4 36.91 45.89 38.46 41.77" in his


def _almond_top() -> float:
    """The white's top straight above the eye's centre, from atlasAlmond's upper curve."""
    m = re.search(r"const ox = cx - ([0-9.]+) \* side;\s+const ix = cx \+ ([0-9.]+) \* side;", ATLAS)
    ox, ix = -float(m.group(1)), float(m.group(2))
    q = re.search(r"upper: `M\$\{ox\} \$\{cy - ([0-9.]+)\}Q\$\{cx - ([0-9.]+) \* side\} \$\{cy - ([0-9.]+)\} \$\{ix\} \$\{cy \+ ([0-9.]+)\}`", ATLAS)
    y0, cxo, cy1, y2 = -float(q.group(1)), -float(q.group(2)), -float(q.group(3)), float(q.group(4))
    lo, hi = 0.0, 1.0
    for _ in range(60):  # the t where the curve crosses x = cx
        t = (lo + hi) / 2
        x = (1 - t) ** 2 * ox + 2 * (1 - t) * t * cxo + t * t * ix
        lo, hi = (t, hi) if x < 0 else (lo, t)
    return (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy1 + t * t * y2


def _ink_top() -> float:
    m = re.search(r'class: "atl-ink", cx, cy: cy - ([0-9.]+), rx: [0-9.]+, ry: ([0-9.]+) \}, iris\);\n\s+atlasMake\("circle", \{ class: "atl-catch", cx: cx - 1.9', ATLAS)
    return -float(m.group(1)) - float(m.group(2))


def test_his_juggle_look_stops_short_of_the_lid():
    top = _almond_top()
    assert -4.4 < top < -4.1
    his = re.search(r'#nm-buddy\.nmb-act-juggle \.nm-atlas\[data-atlas-look="masculine"\] \.atl-pupil \{ --atl-py: (-?[0-9.]+)px; \}', LAZY)
    assert his, "a masculine juggle pupil rule"
    clear = _ink_top() + float(his.group(1)) - top
    assert 0.5 <= clear <= 0.8, clear
    # Still a look up: the ink rises at least 0.6 from rest.
    assert float(his.group(1)) <= -0.6


def test_her_juggle_eyes_are_unchanged():
    assert "#nm-buddy.nmb-act-juggle .nm-atlas .atl-pupil { --atl-px: 0px; --atl-py: -1.6px; }" in LAZY
    assert 'data-atlas-look="feminine"] .atl-pupil' not in LAZY


def test_his_happy_and_determined_read_from_calm():
    # 1607 d, measured at 1x on busts (busts, a throwaway sweep): his face moved
    # from calm by 15.4 (determined, 40 px) and 15.7 and 15.5 (happy, 72 and
    # 120 px), under her least (16.4 to 18.8). Smiling eyes (the lower lid up
    # 0.42, the brows up 1.8) and a lower, keener brow for determined bring
    # his least to 17.6, 20.6 and 20.5.
    def mood(name: str) -> str:
        return re.search(rf'\.nm-atlas\[data-atlas-look="masculine"\]\[data-atlas-mood="{name}"\] \{{([^}}]*)\}}', CSS).group(1)

    # The upper lid stays up (0, as the shared happy has it), so the squint
    # from below leaves the eye open (tests/test_atlas_lids_1301.py).
    assert "--atl-lid: 0; --atl-low: 0.42; --atl-brow-y: -1.8px;" in mood("happy")
    assert "--atl-low: 0.3; --atl-knit: 2deg; --atl-brow-y: 0.4px;" in mood("determined")


def test_his_confused_tilts_the_other_way_from_curious():
    # 1607 d, the coordinator's second note: curious and confused were his
    # closest pair (11.7 to 11.9 at 40/72/120 px, mean grey difference on
    # busts), both heads tilted the same way (-10 and -8 degrees). His
    # confused tilts 9 the other way: 37.3, 32.6 to 34.4 and 58.5 to 62.1
    # over two runs, and no pair of his moods under 15 at any size.
    def tilt(rule: str) -> float:
        return float(re.findall(r"--atl-tilt:\s*(-?[0-9.]+)deg", rule)[-1])

    curious = re.search(r'\n\.nm-atlas\[data-atlas-mood="curious"\] \{([^}]*)\}', CSS).group(1)
    confused = re.search(r'\.nm-atlas\[data-atlas-look="masculine"\]\[data-atlas-mood="confused"\] \{([^}]*)\}', CSS).group(1)
    assert tilt(curious) <= -8 and tilt(confused) >= 8
