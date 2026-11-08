"""Generated looks that read wrong at 64 and 128 px (INBOX 1696 r).

Every look part (`PROFILE_LOOK_PARTS`) and every creature was drawn as the
companion figure at 64 and 128 px, light and dark
(`docs/roadmap/agent-remaining/atlasf1696-1108c.md` lists each row). The
worst three are pinned here:

- the unicorn's rainbow mane was five strands behind the head; only the
  outermost, blue, showed past its edge, a grey scythe on its right side;
- the headband (karate) and the bandana were the same red band with the
  same tails, two picks that drew one thing;
- the dress was the tee with a white stripe: nothing said dress.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _numbers(d: str) -> list[tuple[float, float]]:
    vals = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    return list(zip(vals[0::2], vals[1::2]))


def test_the_unicorns_rainbow_is_a_forelock_in_front_not_a_sliver_behind() -> None:
    m = re.search(r"const forelock = \[([^\]]+)\];", APP)
    assert m, "the rainbow forelock's strands"
    strands = re.findall(r'"(M[^"]+)"', m.group(1))
    assert len(strands) == 5
    for d in strands:
        for x, y in _numbers(d):
            # Inside the 64-wide box, on the crown: above the brows (21.5)
            # and the eyes (30), so the face stays clear.
            assert 4 <= x <= 60, (d, x)
            assert 0 <= y <= 24, (d, y)
    block = APP[m.start() : m.start() + 900]
    assert "top)" in block and "back)" not in block, "drawn in front of the head"
    # Replaced, not layered: the strands behind the head are gone.
    assert "${40 + i * 3} ${2 + i * 2}" not in APP


def test_the_headband_and_the_bandana_are_two_things() -> None:
    at = APP.index('} else if (kind === "headband") {')
    head = APP[at : APP.index("} else if", at + 10)]
    bandana = APP[APP.index('} else if (kind === "bandana") {') : at]
    # A karate band: white, a red sun at the front, long tails; the bandana
    # stays the red band with a knot.
    assert '"#f5f4ef"' in head and "#e8364f" in head
    assert '"#e2574c"' in bandana and "#f5f4ef" not in bandana.split("make(", 2)[1]


def test_the_dress_flares_past_the_body() -> None:
    at = APP.index('} else if (outfit === "dress") {')
    block = APP[at : APP.index("} else {", at)]
    skirt = re.search(r'd: "(M[^"]+Z)", fill: cloth[^}]*\}, torso\)', block)
    assert skirt, "a skirt drawn in the torso, outside the body's clip"
    pts = _numbers(skirt.group(1))
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    # The body is 8.5 to 55.5 wide at its hips and ends at 75: the hem is
    # wider than that and lower, inside the 64 by 92 box.
    assert min(xs) < 8 and max(xs) > 56, xs
    assert max(ys) > 76 and max(ys) < 86, ys
    assert min(xs) >= 1 and max(xs) <= 63, xs
