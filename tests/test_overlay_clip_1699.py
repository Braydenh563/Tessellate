"""INBOX 1699 (the owner, 2026-11-09, Windows): "the bottom of desktop companion atlas's tail gets clipped". The hanging
frame's tail coil ends 2 px (96 dpi) above the canvas bottom, and the flow warp moves the lower body down by up to
`FLOW_MAX` px, so the coil was cut by a straight edge. Every frame, drawn at the largest flow and the extreme poses, keeps
its solid pixels off the canvas edge."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import sprites as sp


@pytest.fixture(scope="module")
def spr() -> sp.SpriteSet:
    return sp.SpriteSet("masculine")


def _extremes() -> list[tuple[int, ...]]:
    big = round(bh.FLOW_MAX * sp.FLOW_Q)
    out = []
    for tip, mid, rise in ((big, big, big), (-big, -big, -big), (big, -big, big), (0, 0, big), (-big, big, -big)):
        out.append((tip, mid, rise) * bh.FLOW_BANDS)
    return out


def _edge_alpha(frame: sp.Frame) -> int:
    """The most alpha on the canvas's outermost rows and columns (what a straight clip leaves behind)."""
    w, h, a = frame.width, frame.height, frame.bgra[3::4]
    rows = a[:w] + a[(h - 1) * w:]
    cols = a[0::w] + a[w - 1::w]
    return max(max(rows), max(cols))


@pytest.mark.parametrize("dpi", [96, 192])
@pytest.mark.parametrize("flip", [False, True])
def test_no_frame_touches_the_canvas_edge_at_the_largest_flow(spr: sp.SpriteSet, dpi: int, flip: bool) -> None:
    names = ["hang", "held", "stand", "sit", "idle0", "look", "hop", "land"] if dpi == 192 else spr.available()
    for name in names:
        if name not in spr.available():
            continue
        for flow in _extremes():
            # the hanging pendulum's hem (`engine.HANG_SWING` 9 px, a grown wind-up half as much again) either way
            for pose in ((1.0, 1.0, 0.0, 0.0),) + (((1.0, 1.0, 0.0, 13.0), (1.0, 1.0, 0.0, -13.0)) if name == "hang" else ()):
                f = spr.posed(name, dpi, flip, pose, flow)
                assert _edge_alpha(f) < sp.ALPHA_FLOOR, (name, dpi, flip, flow[:3], pose, f.box, (f.width, f.height))
