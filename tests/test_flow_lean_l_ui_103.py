"""L-ui-modernisation-103: the follow-through is capped by the angle it bends the streams, not by px.

Source text: "the follow-through clamp (FLOW_MAX 6 px) bends the lower streams to 7.2 to 7.7 degrees ... Recommendation:
clamp the follow-through by angle (a 4 degree cap at the tips), not by px, so a fast turn still lags but never bends
the streams past the posed worst" (INBOX 615 and 619: never more than 4 degrees off the torso; INBOX 1833). The angle is
measured the way tests/test_flow_reach_l_ui_100.py measures it, here on the whole view a fast move gives.
"""

from __future__ import annotations

import math

import pytest
from tessellate.core.overlay import behaviour as bh, sprites

LOOKS = ("masculine", "feminine")


def _angle(look: str, flow: tuple[int, ...]) -> float:
    """The hem's worst lean off the torso for a `Flow.view` tuple, degrees (the stand frame at 192)."""
    s = sprites.SpriteSet(look)
    base = s.frame("stand", 192, False)
    left, top, right, bottom = base.box
    scale = base.width / s._load("stand").size[0]
    rows = [round(i * base.height / sprites.POSE_STRIPS) for i in range(sprites.POSE_STRIPS)] + [base.height]
    edges = [0.0] + [float(round(left + (right - left) * j / bh.FLOW_BANDS)) for j in range(1, bh.FLOW_BANDS)] + [float(base.width)]
    field = sprites.flow_offsets(flow, edges, rows, (left, top, right, bottom), scale)
    waist = top + (bottom - top) * sprites.FLOW_WAIST
    hem = max(j for j, y in enumerate(rows) if y <= bottom)
    start = min(j for j, y in enumerate(rows) if y > waist)
    out = 0.0
    for col in range(len(edges)):
        for row in range(start, hem + 1):
            dx = field[row][col][0] - field[start - 1][col][0]
            out = max(out, math.degrees(math.atan2(abs(dx), rows[row] - rows[start - 1])))
    return out


def _fast_turns(frame: str, lower: str = "") -> list[tuple[int, ...]]:
    """A fixed-clock run of hard turns: 1,200 px/s one way, then the other, every 0.4 s for 8 s, a view each frame."""
    flow = bh.Flow(seed=103)
    out = []
    for n in range(480):
        t = n / 60
        vx = 1200.0 if int(t / 0.4) % 2 == 0 else -1200.0
        flow.step(1 / 60, vx, -300.0 if n % 90 < 45 else 300.0)
        out.append(flow.view(t, frame=frame, lower=lower, side=1.0 if vx > 0 else -1.0))
    return out


def test_source_text_the_cap_is_four_degrees() -> None:
    """Source text: "a 4 degree cap at the tips"."""
    assert bh.FLOW_LEAN == 4.0


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize(("frame", "lower"), [("", ""), ("stand", ""), ("walk_0", "billow"), ("hop_0", "hem_kick")])
def test_source_text_a_fast_move_never_bends_the_streams_past_four_degrees(look: str, frame: str, lower: str) -> None:
    """Source text: "never bends the streams past the posed worst": every view of the run stays under 4 degrees
    (7.17 masculine and 7.67 feminine with the 6 px clamp reached)."""
    worst = max(_angle(look, v) for v in _fast_turns(frame, lower)[::3])
    assert worst < bh.FLOW_LEAN, worst


def test_source_text_a_fast_turn_still_lags() -> None:
    """Source text: "so a fast turn still lags": the follow-through still carries the tips well past the ambient sway."""
    views = _fast_turns("")
    tips = [abs(v[k * sprites.FLOW_FIELDS]) / bh.FLOW_Q for v in views for k in range(bh.FLOW_BANDS)]
    assert max(tips) > bh.FLOW_TIP + 1.5, max(tips)
