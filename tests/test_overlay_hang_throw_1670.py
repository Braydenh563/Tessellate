"""INBOX 1670 (owner, 12:20Z): "it was hanging but then I threw it down and now it is stuck like
this" (the arms-up hang pose, in mid-air). A hang, a throw down from it and the landing must end
in a rest pose on the ground, for a floater and a walker."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]


def hang(gait: str) -> tuple[Engine, float]:
    e = Engine(SIZE, ONE, rng=random.Random(2), home=(800, 920), hang_top=0.195, gait=gait)
    e.climb_ready = float("inf")
    e._perform("hang", 1.0)
    t = 1.0
    while e.state != "hang" and t < 30:
        t += 0.016
        e.update(t)
    assert e.state == "hang"
    for _ in range(30):
        t += 0.016
        e.update(t)
    return e, t


@pytest.mark.parametrize("gait", ["float", "walk"])
@pytest.mark.parametrize("fling", [0, 900, 2500])
def test_a_hanger_thrown_down_ends_at_rest_on_the_ground(gait: str, fling: int) -> None:
    e, t = hang(gait)
    sx, sy = int(e.x + SIZE[0] / 2), int(e.y + SIZE[1] / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    steps = 12
    for i in range(1, steps + 1):  # drag down, then let go at speed (a throw down)
        t += 0.008
        e.update(t, event=("move", sx, sy + 40 * i + fling * 0.008 * i))
    t += 0.008
    e.update(t, event=("up", sx, sy + 40 * steps + fling * 0.008 * steps + fling * 0.008))
    frames = set()
    for _ in range(1500):
        t += 0.016
        out = e.update(t)
        frames.add(out.frame)
        if e.state in ("stand", "sit", "sleep") and e.vx == e.vy == 0:
            break
    for _ in range(60):  # and it stays so
        t += 0.016
        out = e.update(t)
    assert e.state in ("stand", "sit", "sleep"), e.state
    assert out.frame != "hang" and not out.frame.startswith("spin")
    assert e.y >= e.ground_y() - 4.0 * 1.0, (e.y, e.ground_y())
    assert e.hang_on is None


def test_the_in_app_companion_lets_go_of_the_hang_pose_when_it_is_picked_up() -> None:
    """The in-app half of the same report: the drag's halt cleared lie and curl but not hang, so
    the arms-up pose rode the whole throw."""
    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    halt = js[js.index("function nameMarkBuddyHalt(buddy)"):]
    halt = halt[: halt.index("\n}\n")]
    assert 'buddy.dataset.pose === "hang"' in halt and 'nmb.pose = "float"' in halt
    assert '"nmb-climb"' in halt


@pytest.mark.parametrize("look", ["masculine", "feminine"])
@pytest.mark.parametrize("gait", ["float", "walk"])
def test_a_figure_thrown_down_to_the_floor_settles_there_with_the_shipped_frames(look: str, gait: str) -> None:
    """The desktop half of the report: thrown down, a floater stopped at the limit the tumble's
    drawn box allows (a few px above its rest line, the box being taller than the figure) and
    stayed in the limp 'held' pose in mid-air above the taskbar for good."""
    from tessellate.core.overlay.sprites import IDLE_COUNT, SpriteSet

    spr = SpriteSet(look)
    mon = [Monitor((0, 0, 2560, 1464), 192)]
    size = spr.size(192)
    e = Engine(size, mon, rng=random.Random(4), gait=gait, hang_top=spr.top_share("hang"), idle_frames=IDLE_COUNT, home=(900, 1200))
    e.set_metrics(spr.metrics(192))
    e.climb_ready = e.big_ready = float("inf")
    t = 1.0
    sx, sy = int(e.x + size[0] / 2), int(e.y + size[1] / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, 8):  # a quick pull down and across, let go at speed
        t += 0.01
        e.update(t, event=("move", sx + 20 * i, sy - 300 + 150 * i))
    t += 0.01
    e.update(t, event=("up", sx + 160, sy + 750))
    for _ in range(600):
        t += 0.016
        out = e.update(t)
        if e.state == "stand":
            break
    assert e.state == "stand", (e.state, out.frame, e.y, e.ground_y())
    assert out.frame != "held" and abs(e.y - e.ground_y()) < 1.0
