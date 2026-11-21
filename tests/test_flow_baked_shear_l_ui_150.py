"""Source text: the shear table is checked against atlas-life.js's own state rows, the one place the app's lower-box shear
is written down (the browser is not run here); the rest measures the shipped frames.

L-ui-modernisation-150: the lean a desk frame bakes into its lower body counts inside the follow-through's 4 degrees.

The shipped frames carry the app's first arrangement of their pose (decision 7, L-ui-modernisation-57): the lower box
sheared `0.4 * (skew - rot)` degrees off the torso (atlas-life.js `ATLAS_LOWER_STATES`, row 0). `behaviour.Flow` bends
the streams on top of that picture, so toward the baked side its lean takes only what is left of 4 degrees (INBOX 615
and 619: never more than 4 off the torso), measured on each shipped frame's own picture.
"""

from __future__ import annotations

import functools
import math
import re
from pathlib import Path

import pytest
from tessellate.core.overlay import behaviour as bh, sprites

ROOT = Path(__file__).resolve().parents[1]
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")
#: The lower state the app gives each frame family while the desk captures it (`atlasLowerState` on the frame's pose
#: and classes, read from the capture's DOM dump).
STATE = {
    "stand": "idle", "blink": "idle", "look": "idle", "idle": "idle", "walk": "idle", "hop": "idle", "land": "idle",
    "card": "idle", "sit": "sit", "meditate": "sit", "sleep": "lie", "hang_sloth": "lie", "held": "walk",
    "fall": "startle", "tumble": "startle", "dangle": "dangle", "kick": "dangle", "hang": "hang", "lean": "lean",
    "back_float": "drift", "wave": "gesture",
}
FRAMES = tuple(n for n in (*sprites.FRAME_NAMES, *sprites.EXTRA_FRAMES) if not n.startswith("spin"))


def _row0(state: str) -> list[float]:
    m = re.search(rf"\b{state}: \{{ ms: \d+, ease: \"[^\"]+\", v: \[\[([^\]]+)\]", LIFE)
    assert m, state
    return [float(x) for x in m.group(1).split(",")]


def test_source_text_the_table_is_the_apps_first_row() -> None:
    """Source text: the shear is the app's own (`skewX((skew - rot) * way * 0.4)` on the lower boxes), row 0 of the
    frame's state, so a retuned row in atlas-life.js has to move the table with it."""
    assert "go(el, `skewX(${atlasFix((skew - rot) * way * 0.4)}deg)" in LIFE
    table = {r[0]: r[1] for r in bh.FLOW_BAKED}
    assert set(table) == set(STATE)
    for prefix, state in STATE.items():
        rot, _sx, _sy, skew, _tail = _row0(state)
        assert abs(table[prefix]) == pytest.approx(abs(0.4 * (skew - rot)), abs=0.01), prefix


def test_every_shipped_frame_has_a_row_and_the_longest_prefix_names_it() -> None:
    """`hang_sloth` lies, `hang_one` hangs, `idle7` and `stand` are idle; a frame with no row bakes nothing."""
    table = {r[0]: r[1] for r in bh.FLOW_BAKED}
    assert all(bh.flow_baked(n)[0] for n in FRAMES)
    assert bh.flow_baked("hang_sloth")[0] == table["hang_sloth"]
    assert bh.flow_baked("hang_one")[0] == table["hang"]
    assert bh.flow_baked("idle7") == bh.flow_baked("stand")
    assert bh.flow_baked("spin3") == (0.0, bh.FLOW_FREE)


def _angle(look: str, frame: str, tip: float, mid: float, rise: float) -> float:
    """The hem's worst lean off the waist on `frame`'s own picture for one tip, middle and rise in px on every strand
    (the method of tests/test_flow_reach_l_ui_100.py)."""
    s = sprites.SpriteSet(look)
    base = s.frame(frame, 192, False)
    left, top, right, bottom = base.box
    scale = base.width / s._load(frame).size[0]
    worst = tuple(v for _ in range(bh.FLOW_BANDS) for v in (round(tip * bh.FLOW_Q), round(mid * bh.FLOW_Q), round(rise * bh.FLOW_Q), 0, 10))
    rows = [round(i * base.height / sprites.POSE_STRIPS) for i in range(sprites.POSE_STRIPS)] + [base.height]
    edges = [0.0] + [float(round(left + (right - left) * j / bh.FLOW_BANDS)) for j in range(1, bh.FLOW_BANDS)] + [float(base.width)]
    field = sprites.flow_offsets(worst, edges, rows, (left, top, right, bottom), scale)
    waist = top + (bottom - top) * sprites.FLOW_WAIST
    hem = max(j for j, y in enumerate(rows) if y <= bottom)
    start = min(j for j, y in enumerate(rows) if y > waist)
    out = 0.0
    for col in range(len(edges)):
        for row in range(start, hem + 1):
            dx = field[row][col][0] - field[start - 1][col][0]
            out = max(out, math.degrees(math.atan2(abs(dx), rows[row] - rows[start - 1])))
    return out


@functools.cache
def _lean(frame: str, side: float, toward: bool) -> tuple[float, float, float]:
    """Every strand's largest tip and middle toward (or away from) the baked side over 60 s, the follow-through thrown
    to the end of its travel both ways, every lower state; and the largest rise: the posed worst, all at once."""
    sign = 1.0 if -side * bh.flow_baked(frame)[0] >= 0 else -1.0
    sign = sign if toward else -sign
    tip = mid = rise = 0.0
    for lower in ("", *bh.FLOW_LOWER):
        for push in (bh.FLOW_MAX, -bh.FLOW_MAX):
            f = bh.Flow(seed=7)
            for k in range(120):
                for row in f.pos:
                    row[0] = push
                v = f.view(k * 0.5, frame=frame, lower=lower, side=side)
                for i in range(bh.FLOW_BANDS):
                    tip = max(tip, sign * v[5 * i] / bh.FLOW_Q)
                    mid = max(mid, sign * v[5 * i + 1] / bh.FLOW_Q)
                    rise = max(rise, v[5 * i + 2] / bh.FLOW_Q)
    return tip, mid, rise


def _family(frame: str) -> str:
    """One frame per row of `FLOW_BAKED` and `FLOW_POSE` together: the streams are the same on all of them."""
    pose = next((k for k, *_ in bh.FLOW_POSE if frame.startswith(k)), "")
    return f"{bh.flow_baked(frame)}|{pose}"


@pytest.mark.xfail(
    strict=True,
    reason="L-ui-modernisation-150 and 152: passes on the re-rendered pose-arranged frames; the shipped frames are the old render",
)
@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_baked_lean_and_the_flow_stay_inside_four_degrees(look: str) -> None:
    """On every shipped frame, either way the figure faces: toward the frame's own lean the streams take what is left of
    4 degrees, and away from it they lean past the torso by less than 4 (the baked lean taken back first)."""
    first: dict[str, str] = {}
    bad = []
    for frame in FRAMES:
        rep = first.setdefault(_family(frame), frame)
        baked = abs(bh.flow_baked(frame)[0])
        if baked >= bh.FLOW_LEAN:
            continue  # past 4 by itself (`held`): the test below, and L-ui-modernisation-170 for the frame
        for side in (1.0, -1.0):
            toward = _angle(look, frame, *_lean(rep, side, True))
            away = _angle(look, frame, *_lean(rep, side, False))
            if toward + baked >= bh.FLOW_LEAN or away - baked >= bh.FLOW_LEAN:
                bad.append((frame, side, round(toward, 2), round(away, 2), baked))
    assert not bad, bad


def test_a_frame_that_bakes_past_four_takes_no_lean_toward_it() -> None:
    """`held` (the walk state's row: 6 degrees) is past the join's 4 by itself: the streams lean only away from it."""
    assert abs(bh.flow_baked("held")[0]) > bh.FLOW_LEAN
    for side in (1.0, -1.0):
        tip, mid, _rise = _lean("held", side, True)
        assert tip <= 0.0 and mid <= 0.0, (side, tip, mid)
