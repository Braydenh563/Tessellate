"""S16 / 1692 e/n / 1683 c (owner-asks audit): "the lower body and nebula change little per pose" on the desk. The desk draws
them live per pose (`Flow.view(frame=...)` into `SpriteSet.posed`). Measured on the real feminine stand frame at 96 dpi:
the lower half is 2085 opaque pixels and each pose moves 14 (hang) to 52 (hop, fall) of them, so the pose is in the
silhouette but subtle. This pins that each pose does change the drawn silhouette and no two flows draw the same."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import sprites
from tests.test_overlay_sprites import DIR

POSES = ("sleep", "sit", "hang", "wave", "walk", "hop")


def _lower_mask(spr: sprites.SpriteSet, flow: tuple[int, ...]) -> list[bool]:
    f = spr.posed("stand", 96, False, (1.0, 1.0, 0.0, 0.0), flow)
    return [a > 127 for a in f.bgra[3::4][(f.height // 2) * f.width :]]


def _settled(frame: str) -> tuple[int, ...]:
    flow = bh.Flow()
    for i in range(100):
        view = flow.view(100.0 + i * 0.04, frame=frame)
    return view


@pytest.mark.parametrize("look", sprites.LOOKS)
def test_each_pose_draws_a_lower_silhouette_unlike_the_bare_one_and_the_others(look: str) -> None:
    spr = sprites.SpriteSet(look, DIR)
    bare = _lower_mask(spr, _settled("stand"))
    masks = {p: _lower_mask(spr, _settled(p)) for p in POSES}
    for p, m in masks.items():
        assert sum(a != b for a, b in zip(m, bare)) >= 8, (look, p, "the pose leaves the lower body as the idle one")
    for i, p in enumerate(POSES):
        for q in POSES[i + 1 :]:
            assert masks[p] != masks[q], (look, p, q)
