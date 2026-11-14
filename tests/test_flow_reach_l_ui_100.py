"""L-ui-modernisation-100: the lower body's sway is large enough to see on the desk and still inside the join's 4 degrees.

Source text: "Atlas lower-body wisp and ribbon sway is 4 px: too small to see on the desk ... Recommendation (taken):
FLOW_TIP 3.5 (about 2.6 degrees) with FLOW_RISE in proportion, the angle test widened to the pose (kick 1.7) and
arrival worst cases, still under 4" (INBOX 615 and 619: never more than 4 degrees off the torso; INBOX 1833).
"""

from __future__ import annotations

import math

import pytest
from tessellate.core.overlay import behaviour as bh, sprites

LOOKS = ("masculine", "feminine")


def _angle(look: str, tip: float, mid: float, rise: float) -> float:
    """The hem's worst lean off the torso, the method of tests/test_flow_1683.py, for a tip, middle and rise in px."""
    s = sprites.SpriteSet(look)
    base = s.frame("stand", 192, False)
    left, top, right, bottom = base.box
    scale = base.width / s._load("stand").size[0]
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


def test_source_text_flow_tip_3_5_with_the_rise_in_proportion() -> None:
    """Source text: "FLOW_TIP 3.5 (about 2.6 degrees) with FLOW_RISE in proportion"."""
    assert bh.FLOW_TIP == 3.5
    assert bh.FLOW_RISE == pytest.approx(1.1 * 3.5 / 2.2, abs=0.01)


@pytest.mark.parametrize("look", LOOKS)
def test_source_text_the_ambient_sway_is_about_two_and_a_half_degrees(look: str) -> None:
    """Source text: "about 2.6 degrees": measured 2.36 masculine and 2.54 feminine (1.42 and 1.52 at 2.2)."""
    a = _angle(look, bh.FLOW_TIP, bh.FLOW_TIP * 0.65, bh.FLOW_RISE)
    assert 2.2 < a < 3.0, a


@pytest.mark.parametrize("look", LOOKS)
def test_source_text_the_posed_worst_stays_under_four_degrees(look: str) -> None:
    """Source text: "the angle test widened to the pose ... worst cases, still under 4": the arrangement's lean on the
    sway's share, plus the largest lean a lower-body state adds (`FLOW_LOWER`), every strand at once."""
    lean = max(v[2] for v in bh.FLOW_LOWER.values())
    rise = max(v[3] for v in bh.FLOW_LOWER.values())
    tip = bh.FLOW_TIP * bh.FLOW_ARR_SWAY + bh.FLOW_ARR_TIP + lean
    mid = bh.FLOW_TIP * bh.FLOW_ARR_SWAY * 0.65 + bh.FLOW_ARR_TIP * 0.6 + lean
    a = _angle(look, tip, mid, bh.FLOW_RISE + bh.FLOW_ARR_RISE + rise)
    assert a < 4.0, a
