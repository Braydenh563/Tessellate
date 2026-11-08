"""INBOX 1696 gg, the owner, of the masculine Atlas: "that semicircular arc or
curve on the top of masculine atlas's head looks like female hair or a tiara".

Measured first (scratchpad/probe in the agent's scratch dir, the same sampling
as below): his crest was four locks and a mass, each a half circle, turning 157
to 203 degrees from root to tip, 41 to 53 units long and falling to y 43 on his
left (the chin is at about y 37): a long ponytail curled over the crown, which
at 64 px is one pale arc over the head. Now it is a short swept crest: each
lock rises from inside the crown and sweeps over to his left, ends above the
eyes and just past the skull, with a tapered tip, so it reads as his short cut
beside her long hair.

These read the rig's own centrelines (`ATLAS_LOOKS.masculine.locks` and
`head`), the lines the lock fills are built round (`atlasStem`).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _look(name: str) -> str:
    start = ATLAS.index(f"  {name}: {{", ATLAS.index("const ATLAS_LOOKS = {"))
    return ATLAS[start : ATLAS.index("\n  },\n", start)]


def _locks(look: str, block: str) -> list[tuple[list[list[float]], float, bool]]:
    body = _look(look)
    part = body[body.index(f"    {block}: [") :]
    part = part[: part.index("    ],\n")]
    found = re.findall(r"seg: (\[\[.*?\]\]), w: \[([0-9.]+), [0-9.]+\](, mass: true)?", part)
    return [(json.loads(seg), float(w), bool(mass)) for seg, w, mass in found]


def _points(seg: list[list[float]], n: int = 30) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for x0, y0, x1, y1, x2, y2, x3, y3 in seg:
        for k in range(n + 1):
            t = k / n
            u = 1 - t
            pts.append((u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3))
    return [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]


def _turn(pts: list[tuple[float, float]]) -> float:
    total = 0.0
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        d1 = math.atan2(b[1] - a[1], b[0] - a[0])
        d2 = math.atan2(c[1] - b[1], c[0] - b[0])
        total += (d2 - d1 + math.pi) % (2 * math.pi) - math.pi
    return abs(math.degrees(total))


def _length(pts: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def test_his_crest_is_a_short_sweep_not_a_curled_arc():
    for block in ("locks", "head"):
        locks = _locks("masculine", block)
        assert len(locks) >= 3, block
        for seg, _w, mass in locks:
            pts = _points(seg)
            # A half circle turns 180; a sweep that lifts and lies over turns well under it.
            assert _turn(pts) <= 110, (block, seg[0][:2], round(_turn(pts)))
            assert _length(pts) <= 30, (block, seg[0][:2], round(_length(pts), 1))
            # Above the eyes (their row is y 27, the brows 20.6) and only just past the skull (its right edge 44.6).
            assert max(y for _, y in pts) <= 18, (block, seg[0][:2])
            assert max(x for x, _ in pts) <= 53, (block, seg[0][:2])
            # Swept: every lock ends on his left of where it rises, by a third of the head or more.
            assert pts[-1][0] - pts[0][0] >= 9, (block, seg[0][:2])
            # Rooted inside the head (centre 31 23, radius 13), as hers are, so no root end shows.
            x, y = seg[0][:2]
            assert (x - 31) ** 2 + (y - 23) ** 2 < 13**2, (block, x, y)
        # Not a dome over the crown: the crest's highest point is a tip on his left side (x 40 or more, the
        # crown's middle is 31), and the soft mass under the locks stays below the tips.
        tips = [_points(seg) for seg, _w, mass in locks if not mass]
        top = min((p for pts in tips for p in pts), key=lambda p: p[1])
        assert top[0] >= 40, (block, top)
        mass_top = min(y for seg, _w, mass in locks if mass for _, y in _points(seg))
        assert mass_top >= top[1] + 5, (block, mass_top, top)


def test_her_long_hair_is_unchanged_by_his_cut():
    # The owner: "I just prefer the female version a lot more". Her locks still stream down her back.
    for seg, _w, mass in _locks("feminine", "locks"):
        if mass:
            continue
        assert max(y for _, y in _points(seg)) >= 50
