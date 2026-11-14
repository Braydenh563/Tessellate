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


# --- rows 4 to 12 (atlasf1696-1108c.md) --------------------------------------


def _block(start: str, end: str) -> str:
    at = APP.index(start)
    return APP[at : APP.index(end, at + len(start))]


def test_the_tiara_is_a_thin_band_with_three_points_and_a_gem() -> None:
    block = _block('} else if (kind === "tiara") {', "} else if (kind ===")
    ds = re.findall(r'"(M[^"]+Z)"', block)
    assert len(ds) == 4, "a band and three points"
    band, *points = ds
    ys = [y for _, y in _numbers(band)]
    assert max(ys) - min(ys) <= 5, "the band is thin"
    tips = sorted(min(y for _, y in _numbers(d)) for d in points)
    assert len(points) == 3 and tips[0] <= -3 and tips[1] >= -1, tips
    assert "#e36fa6" in block and "r: 1.7" in block, "a gem"


def test_the_sweater_has_a_ribbed_hem_and_cuffs() -> None:
    block = _block('} else if (outfit === "sweater") {', '} else if (outfit === "dress") {')
    assert "x += 3" in block and "L${x} 78" in block, "rib lines running down the hem"
    assert "cuff = {" in block
    arms = _block("if (cuff) {", "if (claw)")
    assert "stroke-width" in arms and "arm)" in arms, "cuffs drawn on the arm so they move with it"


def test_a_raised_gesture_is_drawn_on_the_arm_not_the_hold_pair() -> None:
    # `.nm-figure .nmb-hold { opacity: 0 }` hides the hanging reach only; the
    # gesture is `.nmc-raised` on the right arm, which the figure rotates up.
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".nm-figure .nmb-arm-r.nmc-raised { rotate: -115deg; }" in css
    block = _block('case "thumbsup":', "default:")
    assert 'arm.classList.add("nmc-raised")' in block
    # The digits were 3 units long at 64 px: long enough to read now.
    ry = [float(v) for v in re.findall(r"ry: (\d+(?:\.\d+)?)", block)]
    assert ry and min(ry) >= 4.4, ry


def test_tableflip_draws_a_table_and_the_brush_has_a_head() -> None:
    flip = _block('case "tableflip":', 'case "wave":')
    assert 'shape("rect"' in flip and "for (const lx of [" in flip, "a top and legs, not one bar"
    brush = _block('case "paintbrush":', 'case "hammer":')
    assert "steel" in brush, "a ferrule"
    bristles = re.search(r"d: `M\$\{hx \+ 2\.6\}[^`]+`", brush)
    assert bristles, "bristles as a curved tuft"
    xs = [float(v) for v in re.findall(r"hx \+ (\d+(?:\.\d+)?)", bristles.group(0))]
    assert max(xs) - min(xs) >= 5, "wider than the old 3 unit stump"


def test_the_thermometer_is_not_a_cigarette() -> None:
    block = _block('if (extras.includes("thermometer")) {', "// --- what it wears")
    bulb = re.search(r'make\("circle", \{ cx: ([\d.]+), cy: my, r: ([\d.]+), fill: "#e8364f"', block)
    assert bulb, "a red bulb"
    cx, r = float(bulb.group(1)), float(bulb.group(2))
    assert r >= 2.2, "a big bulb"
    assert cx >= 40, "at the outer end, not the tip held in the mouth"
    assert 'fill: "#ffffff"' not in block, "not a plain white stick"


def test_a_frogs_closed_eyes_sit_on_whites() -> None:
    assert re.search(r'creature\?\.eyesUp && \["happy", "content", "closed", "squeeze"\]\.includes\(s\)\) white\(', APP)


def _luma(hex_: str) -> float:
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luma(a), _luma(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_bat_koala_and_cyclops_hold_three_to_one_on_both_grounds() -> None:
    for name in ("bat", "koala", "cyclops"):
        colour = re.search(rf'  {name}: \{{ head: "(#[0-9a-f]{{6}})"', APP).group(1)
        assert _contrast(colour, "#171a26") >= 3, (name, "dark")
        assert _contrast(colour, "#eef0f6") >= 3, (name, "light")


def test_the_cyclops_eye_is_big_for_the_head() -> None:
    m = re.search(r"creature\?\.oneEye[^\n]+eyes\.push\(\[32, eyeY - 1, ([\d.]+)\]\)", APP)
    assert m and float(m.group(1)) >= 1.8
