"""How a companion travels a far move (INBOX 1305).

The owner: "companion movement for both small and large distances needs a
lot of improvement, and reworking". Measured first (scratchpad/ui-sweeps/
companionpath.js, 1440x900, the frame loop on its position): a move past 480px
was a poof, one frame of 1,000 to 1,330px; a 300px rise was either a glide at
27px a frame or a poof; the throw's flight had five frames over 40px.

`companionPathPlan` (the end of frontend/js/companion-menu.js, lazy) is pure: a move in,
a path out. These run it in node as written over a grid of moves, and check
`nameMarkBuddyGo` (avatars.js) plays it and no longer poofs on distance.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
MENU = (ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8")
#: The planner is the end of the file and touches no DOM, so node runs it alone.
PATH = MENU[MENU.index("const COMPANION_PATH_PEAK") :]
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _plans(moves: list[list[float]], flies: bool = False, size: int = 64) -> list[dict]:
    script = PATH + (
        f"\nconsole.log(JSON.stringify({json.dumps(moves)}.map(([dx, dy]) => "
        f"{{ const p = companionPathPlan(dx, dy, {size}, {str(flies).lower()}); return {{ dx, dy, kind: p.kind, ms: p.ms, peak: p.peak, beat: p.beat, points: p.points, frames: p.frames }}; }})));"
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


# was minus destination: dy > 0 is a rise. Level, rises, short and long drops, both ways across.
GRID = [[dx, dy] for dx in (-1400, -900, -400, -200, 200, 400, 900, 1400) for dy in (-700, -300, -130, -40, 0, 40, 130, 300, 700)]


@needs_node
def test_no_far_move_has_a_frame_over_forty_pixels() -> None:
    # The teleport line. Measured at 60 Hz over the samples, every piece.
    for plan in _plans(GRID):
        pts = plan["points"]
        for a, b in zip(pts, pts[1:]):
            step = ((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5 * 1000 / 60 / (plan["ms"] / (len(pts) - 1))
            assert step <= 31, (plan["dx"], plan["dy"], plan["kind"], step)
        assert plan["peak"] <= 31


@needs_node
def test_a_path_starts_where_it_was_and_ends_on_its_place() -> None:
    for plan in _plans(GRID):
        first, last = plan["points"][0], plan["points"][-1]
        assert (first[1], first[2]) == (plan["dx"], plan["dy"])
        assert (round(last[1], 6), round(last[2], 6)) == (0, 0)
        assert [f["offset"] for f in plan["frames"]][0] == 0 and plan["frames"][-1]["offset"] == 1


@needs_node
def test_the_time_scales_with_distance_and_is_capped() -> None:
    plans = {(p["dx"], p["dy"]): p for p in _plans([[400, 0], [1000, 0], [1400, 0], [-1400, 700]])}
    assert plans[(400, 0)]["ms"] < plans[(1000, 0)]["ms"] <= plans[(1400, 0)]["ms"]
    # About a second across the window, never more than 1.4s on the level or an arc.
    assert plans[(1000, 0)]["ms"] <= 1000
    assert plans[(1400, 0)]["ms"] <= 1300
    assert plans[(-1400, 700)]["ms"] <= 1400
    # A longer run has quicker legs.
    assert plans[(400, 0)]["beat"] < plans[(1400, 0)]["beat"]


@needs_node
def test_the_way_is_a_run_an_arc_or_a_drop_by_the_change_of_level() -> None:
    kinds = {(p["dx"], p["dy"]): p["kind"] for p in _plans([[600, 0], [600, 36], [600, 40], [-600, 300], [300, -400], [900, -300], [100, -130]])}
    assert kinds == {
        (600, 0): "run", (600, 36): "run", (600, 40): "arc", (-600, 300): "arc",
        (300, -400): "drop", (900, -300): "arc", (100, -130): "drop",
    }
    # A flyer floats down; it never drops.
    assert {p["kind"] for p in _plans([[300, -400], [100, -130]], flies=True)} == {"arc"}


@needs_node
def test_an_arc_rises_above_both_ends_and_a_drop_runs_before_it_falls() -> None:
    (arc,) = _plans([[-600, 300]])
    # Going up 300: the jump tops out above the place it lands on (negative y).
    assert min(p[2] for p in arc["points"]) < -20
    (drop,) = _plans([[300, -400]])
    ys = [p[2] for p in drop["points"]]
    xs = [p[1] for p in drop["points"]]
    # It never goes below where it began until it has run out of ground, and x is spent before y.
    corner = next(i for i, p in enumerate(drop["points"]) if abs(p[1]) < 1e-6)
    assert all(y == -400 for y in ys[:corner])
    assert all(abs(x) < 1e-6 for x in xs[corner:])
    assert ys[-1] == 0


@needs_node
def test_a_fall_speeds_up_like_gravity_and_a_run_starts_from_rest() -> None:
    (drop,) = _plans([[0, -400]])
    ys = [p[2] for p in drop["points"]]
    steps = [b - a for a, b in zip(ys, ys[1:])]
    assert steps[0] < steps[len(steps) // 2] < steps[-1]
    (run,) = _plans([[1000, 0]])
    xs = [p[1] for p in run["points"]]
    steps = [a - b for a, b in zip(xs, xs[1:])]
    assert steps[0] < steps[len(steps) // 2] > steps[-1]


def test_go_plays_the_plan_and_a_far_move_no_longer_poofs() -> None:
    go = _fn(AV, "nameMarkBuddyGo")
    assert 'typeof companionPathPlan === "function"' in go
    assert "plan.frames" in go and "plan.ms" in go
    # Out of sight is still a poof; a distance is not.
    assert "!seenFrom || route ===" not in go and "distance > size * NMB_POOF_SIZES" not in go
    assert "!seenFrom" in go
    assert "nameMarkBuddyFarWay" not in AV and "NMB_POOF_SIZES" not in AV


def test_the_plan_is_in_the_lazy_file_that_comes_with_the_mind() -> None:
    assert '"/js/companion-menu.js"' in APP.split("companionMenu:")[1].split("\n")[0]
    assert "function companionPathPlan(" in PATH


def test_a_throw_is_never_drawn_faster_than_a_frame_of_forty_pixels() -> None:
    # 2.3 px/ms is 38px at 60 Hz; the release clamp and the flight step both use it.
    assert "const NMB_THROW = { max: 2.3," in AV
    assert "k.max / Math.hypot(n.vx, n.vy)" in _fn(AV, "nameMarkBuddyFlightStep")
