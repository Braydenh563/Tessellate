"""INBOX 1607 (b, c, d), the owner, of the masculine Atlas: "the size or shape
or smth of the head looks off and a little creepy", "the connection between
the sholders and the arms could be smoother", "the facial expressions need
some work". The reference is the feminine look.

Measured live first (scratchpad/ui-sweeps/atlasm1108.js and .py; the spec and
the before and after numbers are in docs/roadmap/agent-remaining/atlasm-1108.md):
the head is the same drawing in both looks, so what read as off was (1) a head
on shoulders 1.45 times hers (head over shoulders 1.08 against her 1.56), (2) a
bare egg, 93% of his outline below the brows meeting the background where her
hair frames a fifth of it, and (3) small, wide-set eyes under 22% brows.

These tests read the rig's own numbers (the paths and the CSS that draws
them), sampled the way the sweep samples what renders, so the numbers agree
with the sweep to about 0.01.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")


def _look(name: str) -> str:
    start = ATLAS.index(f"  {name}: {{", ATLAS.index("const ATLAS_LOOKS = {"))
    return ATLAS[start : ATLAS.index("\n  },\n", start)]


def _path(look: str, key: str) -> str:
    return re.search(rf'\b{key}: "([^"]+)"', _look(look)).group(1)


def _arms(look: str) -> dict[str, list[list[float]]]:
    body = _look(look)
    return {
        "l": json.loads(re.search(r"\barmL: (\[\[.*?\]\]),", body).group(1)),
        "r": json.loads(re.search(r"\n    arm: (\[\[.*?\]\]),", body).group(1)),
    }


HEAD = re.search(r'const ATLAS_HEAD_PATH = "([^"]+)"', ATLAS).group(1)


def _sample(d: str) -> list[list[tuple[float, float]]]:
    """An absolute M/C/Z path as polylines, one per subpath, 40 points a curve."""
    toks = re.findall(r"[MCZ]|-?[0-9.]+", d)
    subs: list[list[tuple[float, float]]] = []
    pts: list[tuple[float, float]] = []
    i, cmd = 0, "M"
    while i < len(toks):
        if toks[i] in "MCZ":
            cmd = toks[i]
            i += 1
            if cmd == "Z":
                subs.append(pts)
                pts = []
                continue
        n = 2 if cmd == "M" else 6
        v = [float(x) for x in toks[i : i + n]]
        i += n
        if cmd == "M":
            pts = [(v[0], v[1])]
            continue
        p0 = pts[-1]
        for k in range(1, 41):
            s = k / 40
            u = 1 - s
            pts.append((u**3 * p0[0] + 3 * u * u * s * v[0] + 3 * u * s * s * v[2] + s**3 * v[4], u**3 * p0[1] + 3 * u * u * s * v[1] + 3 * u * s * s * v[3] + s**3 * v[5]))
    if pts:
        subs.append(pts)
    return subs


def _edges(subs):
    for pts in subs:
        yield from zip(pts, pts[1:] + pts[:1])


def _inside(subs, x: float, y: float) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in _edges(subs):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _width_at(d: str, y: float) -> float:
    xs = sorted(x1 + (x2 - x1) * (y - y1) / (y2 - y1) for (x1, y1), (x2, y2) in _edges(_sample(d)) if (y1 > y) != (y2 > y))
    return xs[-1] - xs[0]


def _head_k(look: str) -> float:
    found = re.search(rf'\.nm-atlas\[data-atlas-look="{look}"\]:not\(\.atl-head, \.atl-tiny\) \{{ --atl-head-k: ([0-9.]+); \}}', CSS)
    if found:
        return float(found.group(1))
    return float(re.search(r"\.nm-atlas:not\(\.atl-head, \.atl-tiny\) \{ --atl-head-k: ([0-9.]+); \}", CSS).group(1))


def _head_over_shoulders(look: str) -> float:
    xs = [x for s in _sample(HEAD) for x, _ in s]
    return (max(xs) - min(xs)) * _head_k(look) / _width_at(_path(look, "torso"), 40)


def _bare_below_brows(look: str, below: float = 18.0, out: float = 1.2, n: int = 300) -> float:
    """The share of the head's outline below the brows whose point 1.2 units
    outside (away from the face's middle, 31 24) is not in the hair cap: the
    sweep's `framing` (which also counts the ears, so it reads a little lower)."""
    outline = _sample(HEAD)[0]
    cap = _sample(_path(look, "cap"))
    lengths = [0.0]
    for a, b in zip(outline, outline[1:] + outline[:1]):
        lengths.append(lengths[-1] + math.dist(a, b))
    low = bare = 0
    for i in range(n):
        at = lengths[-1] * i / n
        k = max(j for j in range(len(lengths) - 1) if lengths[j] <= at)
        (ax, ay), (bx, by) = outline[k], outline[(k + 1) % len(outline)]
        f = (at - lengths[k]) / ((lengths[k + 1] - lengths[k]) or 1)
        px, py = ax + (bx - ax) * f, ay + (by - ay) * f
        if py <= below:
            continue
        dx, dy = px - 31, py - 24
        m = out / math.hypot(dx, dy)
        low += 1
        bare += not _inside(cap, px + dx * m, py + dy * m)
    return bare / low


def test_his_head_sits_on_shoulders_in_her_proportion():
    # 1607 b: head over shoulders 1.09 (head 24.4 units at 0.76 on shoulders
    # 17.0 across) against her 1.59; now 1.28 to 1.45, from both ends: his head
    # a little larger (0.8) and his shoulders narrower (15.0). INBOX 614's "make
    # the masculine atlas look hot and 19-21" stays: the V (shoulders over
    # waist) is still wider than her 1.44.
    assert '.nm-atlas[data-atlas-look="masculine"]:not(.atl-head, .atl-tiny) { --atl-head-k: 0.8; }' in CSS
    assert 1.28 <= _head_over_shoulders("masculine") <= 1.45, _head_over_shoulders("masculine")
    assert _head_over_shoulders("feminine") >= 1.5, "hers does not move"
    torso = _path("masculine", "torso")
    waist = min(_width_at(torso, y / 10) for y in range(440, 560))
    assert _width_at(torso, 40) / waist >= 1.5, "the V stays"


def test_his_hair_frames_his_face():
    # 1607 b: his hairline was 14.2 at the face's middle (hers 15.8) and 93% of
    # his outline below the brows met the background (hers 78 to 80%): a bare
    # egg. Now the hairline is lower, still his two swept points, and the cap
    # runs down each temple into a short sideburn that stands just proud of
    # the cheek, so his hair frames the face as hers does.
    cap = _sample(_path("masculine", "cap"))
    hairline = max(y for (x1, y1), (x2, y2) in _edges(cap) if (x1 > 31) != (x2 > 31) for y in [y1 + (y2 - y1) * (31 - x1) / (x2 - x1)])
    assert 15.6 <= hairline <= 16.4, hairline
    assert _bare_below_brows("masculine") <= 0.82, _bare_below_brows("masculine")
    assert max(y for s in cap for _, y in s) >= 26, "a sideburn on each side, to the eye's line"
    # The sideburns stay clear of the eyes (each almond as drawn, at his eye scale).
    scale = float(re.search(r'\.nm-atlas\[data-atlas-look="masculine"\] \.atl-eye \{ scale: ([0-9.]+); \}', CSS).group(1))
    for cx, cy, side in ((24.4, 27, 1), (37.6, 27, -1)):
        for t in range(41):
            u = t / 40
            ox, ix = cx - 5.1 * side, cx + 4.9 * side
            x = (1 - u) ** 2 * ox + 2 * (1 - u) * u * (cx - 0.6 * side) + u * u * ix
            y = (1 - u) ** 2 * (cy - 0.8) + 2 * (1 - u) * u * (cy - 8.2) + u * u * (cy + 0.2)
            assert not _inside(cap, cx + (x - cx) * scale, cy + (y - cy) * scale), (side, t)


def test_his_arms_grow_from_inside_his_narrower_shoulders():
    # With the shoulders in, the arms' roots come in with them (24.6 and 37.4
    # to 25.6 and 36.4, each arm moved whole), so a root stays inside the torso
    # with its arm's outer edge on the body; the CSS turns his arms (and what
    # they hold) about those roots.
    torso = _sample(_path("masculine", "torso"))
    for side, segs in _arms("masculine").items():
        x, y = segs[0][:2]
        assert _inside(torso, x - 1.8, y) and _inside(torso, x + 1.8, y), (side, x)
    (lx, _), (rx, _) = _arms("masculine")["l"][0][:2], _arms("masculine")["r"][0][:2]
    for part in ("arm", "hold"):
        assert f"#nm-buddy .atl-figure .nmb-{part}-l {{ transform-origin: {lx}px 41px; }}" in CSS
        assert f"#nm-buddy .atl-figure .nmb-{part}-r {{ transform-origin: {rx}px 41px; }}" in CSS
    assert f".nm-atlas .nmb-arm-l {{ transform-box: view-box; transform-origin: {lx}px 41px; }}" in CSS


def _mask() -> tuple[str, float, float, float]:
    """The shoulder mask's ellipses: (where their centres come from, cy, rx, ry)."""
    found = re.search(r'for \(const cx of (.+?)\) atlasMake\("ellipse", \{ cx, cy: ([0-9.]+), rx: ([0-9.]+), ry: ([0-9.]+), fill: `url\(#\$\{id\}-shoulderg\)` \}, shoulders\);', ATLAS)
    cy, rx, ry = (float(v) for v in found.groups()[1:])
    return found.group(1), cy, rx, ry


def test_the_shoulder_join_is_placed_from_each_look_s_own_roots():
    # 1607 c ("the connection between the sholders and the arms could be
    # smoother"): the torso's paint laid over each arm's root (`shoulders`)
    # was one placing for both looks, his roots, full only to y 43.5, so his
    # arm's shaded inner edge crossed the torso below it (16 of 28 points
    # read as a line at 1x, atlasm1108.js) and hers sat 1.8 off her roots.
    # Each look's mask now stands on its own arms' roots, deep enough to
    # cover every point of an arm's inner edge that lies inside the torso.
    source, cy, rx, ry = _mask()
    assert "24.6" not in source and "37.4" not in source and "armL[0][0]" in source and "arm[0][0]" in source, source
    full = 0.55  # the gradient's last opaque stop (`shoulderg`)
    for look in ("masculine", "feminine"):
        body = _look(look)
        torso = _sample(_path(look, "torso"))
        w0, w1 = json.loads(re.search(r"armWidth: (\[[^\]]+\])", body).group(1))
        width = lambda t, w0=w0, w1=w1: w0 - (w0 - w1) * min(1, t * 1.15) ** 0.9  # noqa: E731 (atlasLimbTo)
        arms = _arms(look)
        roots = [arms["l"][0][0], arms["r"][0][0]]
        for side, segs in arms.items():
            towards = 1 if side == "l" else -1
            for i in range(61):
                t = i / 60
                k = min(len(segs) - 1, int(t * len(segs)))
                s = t * len(segs) - k
                x0, y0, x1, y1, x2, y2, x3, y3 = segs[k]
                at = lambda s: ((1 - s) ** 3 * x0 + 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s**3 * x3, (1 - s) ** 3 * y0 + 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s**3 * y3)  # noqa: E731
                (ax, ay), (bx, by) = at(max(0, s - 1e-3)), at(min(1, s + 1e-3))
                px, py = at(s)
                n = math.hypot(bx - ax, by - ay)
                # The edge that faces the body's middle.
                nx, ny = (by - ay) / n, -(bx - ax) / n
                if nx * towards < 0:
                    nx, ny = -nx, -ny
                ex, ey = px + nx * width(t) / 2, py + ny * width(t) / 2
                if not _inside(torso, ex, ey) or min(math.dist((ex, ey), p) for p in torso[0]) < 0.4:
                    continue
                r = min(math.hypot((ex - cx) / rx, (ey - cy) / ry) for cx in roots)
                alpha = 1 if r <= full else max(0.0, 1 - (r - full) / (1 - full))
                assert alpha >= 0.6, (look, side, round(ex, 1), round(ey, 1), round(alpha, 2))


def _rule(selector: str) -> str:
    found = re.search(re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert found, selector
    return found.group(1)


def _decl(body: str, prop: str) -> float:
    return float(re.search(rf"(?<![\w-]){prop}:\s*(-?[0-9.]+)", body).group(1))


def test_his_eyes_are_her_size_and_set_as_close():
    # 1607 d: his eyes were 0.84 of the drawing (0.341 of the head's width,
    # the gap between them 0.57 of an eye), hers 0.9 (0.366, 0.47): small
    # eyes set wide on a big face, which is what read as off. The same size
    # now (round 9's smaller eye was for the stare; INBOX 1301's lid fix
    # answered that, so the size can match hers).
    scale = _decl(_rule('.nm-atlas[data-atlas-look="masculine"] .atl-eye'), "scale")
    xs = [x for s in _sample(HEAD) for x, _ in s]
    width = 10.0 * scale  # the almond, 5.1 out and 4.9 in from the eye's centre
    assert 0.36 <= width / (max(xs) - min(xs)) <= 0.37, width / (max(xs) - min(xs))
    gap = (37.6 - 4.9 * scale) - (24.4 + 4.9 * scale)
    assert gap / width <= 0.5, gap / width


def test_his_brows_and_lids_carry_the_mood():
    # 1607 d: his brows were a 22% hairline (the mood's brow moves showed as
    # nothing at the companion's size) and his eyes had no line to frame
    # them where hers have three lashes. Now a brow that is seen (0.6, 1.5
    # wide), drawn a little shorter at the outer end so it reads as a taper,
    # a heavier upper lid line, and one short flick at the outer corner.
    brow = _rule(".nm-atlas .atl-brow-straight")
    assert _decl(brow, "opacity") >= 0.55 and _decl(brow, "stroke-width") >= 1.5, brow
    straight = re.search(r'spec\.brow === "straight"\s*\?\s*`M\$\{x - ([0-9.]+) \* side\} [^Q]*Q[^`]*\$\{x \+ ([0-9.]+) \* side\}', ATLAS)
    outer, inner = (float(v) for v in straight.groups())
    assert outer < inner, "shorter at the outer end"
    liner = _rule('.nm-atlas[data-atlas-look="masculine"] .atl-liner:not(.atl-liner-low)')
    assert _decl(liner, "stroke-width") >= 1.4, liner
    assert 'lashes: "flick",' in _look("masculine") and "lashes: true," in _look("feminine")
    eye = ATLAS[ATLAS.index("function atlasEye(") :]
    eye = eye[: eye.index("\n}\n")]
    assert 'lashes === "flick"' in eye, "one flick for him, her three lashes for her"
    assert "if (lashes === true && !tiny)" in eye, "her resting lashes stay hers"
    lids = ATLAS[ATLAS.index("function atlasLids(") :]
    assert "if (spec.lashes === true && shut === 1)" in lids[: lids.index("\n}\n")]


def test_his_weakest_moods_move_his_face():
    # 1607 d: at 1x his face changed from calm by 12.9 for determined, 17.3
    # for happy and 18.3 for surprised (hers 17.4 at the least): too little
    # to read. With the brows seen, each of his moves a little further, and
    # determined stays keen, never cross (INBOX 1402: no inner end down past
    # 4 degrees in a quiet mood).
    def face(mood: str) -> str:
        return _rule(f'.nm-atlas[data-atlas-mood="{mood}"]') + _rule(f'.nm-atlas[data-atlas-look="masculine"][data-atlas-mood="{mood}"]')

    def last(mood: str, prop: str) -> float:
        return float(re.findall(rf"--atl-{prop}:\s*(-?[0-9.]+)", face(mood))[-1])

    assert last("happy", "low") >= 0.3
    assert last("surprised", "brow-y") <= -4.2
    assert last("determined", "low") >= 0.24 and last("determined", "knit") <= 4
    assert last("worried", "knit") <= -14
