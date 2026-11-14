"""W31 E1, E2 (INBOX 1710, 1711): the desk figure's five new pictures (`dangle`, `kick0`, `kick1`, `hang_one`, `meditate`) and
the acts that draw them. A fixed clock and seeded randomness, the shipped frames' own boxes; real Windows is unverified.

Each act is read where it must fire: the legs-over-the-edge acts only on a window's top (and with room for the hem under it),
the one-handed hang only inside a long calm hang, the meditation on the floor; a look without a picture draws the pose it varies."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import runner, sprites
from tessellate.core.overlay.engine import Monitor, Perch
from tests.test_overlay_ride_1670 import AREA, LOOKS, WIN, make

TICK = 0.1
PERCH_ACTS = ("dangle", "kick_legs")


def perched(look: str, gait: str, seed: int, win: Perch = WIN):
    e, s = make(look, gait, seed)
    e.extra_frames = s.extras()
    e.roam = True
    t = 1.0
    e.update(t)
    e.set_windows([win], t)
    e._stand_on(win, t)
    for _ in range(80):
        t += 1 / 60
        e.update(t)
    assert e.perch is not None
    return e, s, t


def run_acts(e, t: float, n: int, frames: set[str], seat: dict[str, set[float]] | None = None, s=None) -> tuple[float, list[str]]:
    """`n` weighted act picks, each played to its end; the frames drawn are collected (and where the seat was)."""
    chosen: list[str] = []
    for _ in range(n):
        e._perform("rest", t)
        chosen.append(e.act)
        end = t + 45
        while t < end and e.state == "act":
            t += TICK
            out = e.update(t)
            frames.add(out.frame)
            if seat is not None and s is not None and out.frame in sprites.EXTRA_FRAMES:
                seat.setdefault(out.frame, set()).add(round(out.y + s.metrics(96)[("sit", out.flip)][3] - WIN.top, 1))
        e.state_until = 0
    return t, chosen


@pytest.mark.parametrize("look", LOOKS)
def test_every_shipped_look_has_the_five_pictures_on_the_sit_canvas(look: str) -> None:
    s = sprites.SpriteSet(look)
    assert s.extras() == frozenset(sprites.EXTRA_FRAMES) and s.missing() == []
    from PIL import Image

    with Image.open(s.directory / "sit.png") as sit:
        for name in sprites.EXTRA_FRAMES:
            with Image.open(s.directory / f"{name}.png") as im:
                assert im.size == sit.size, name


@pytest.mark.parametrize("look", LOOKS)
def test_the_hem_hangs_under_the_seat_and_the_hands_stay_on_the_edge(look: str) -> None:
    s = sprites.SpriteSet(look)
    box = s.metrics(96)
    sit = box[("sit", False)]
    for name in ("dangle", "kick0", "kick1"):
        b = box[(name, False)]
        assert abs(b[1] - sit[1]) <= 3, (name, b, sit)  # the head where the sit's is
        assert name != "dangle" or b[3] - sit[3] >= 3, (name, b, sit)  # the hem is let down under the seat (a kick swings it about within that)
    # the hands of the one-handed hang meet the edge where the hang's do (the held hand's top row, 2x pixels: within 1 logical px)
    from PIL import Image

    def hand_top(name: str) -> int:
        with Image.open(s.directory / f"{name}.png") as im:
            a = im.convert("RGBA").getchannel("A").point(lambda v: 255 if v >= 128 else 0)
            w = a.size[0]
            return min(y for x0 in range(0, w, 12) if (y := (a.crop((x0, 0, min(w, x0 + 12), a.size[1])).getbbox() or (0, 10**6))[1]) < 10**6)

    assert abs(hand_top("hang_one") - hand_top("hang")) <= 2


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
def test_the_legs_over_the_edge_acts_only_come_on_a_window_top_and_sit_on_its_line(look: str, gait: str) -> None:
    on_top: list[str] = []
    seat: dict[str, set[float]] = {}
    frames: set[str] = set()
    # a walker stays on the window between acts (8 picks each); a floater rests on it for the first act only, then goes home
    for seed in range(1, 13 if gait == "walk" else 61):
        e, s, t = perched(look, gait, seed)
        t, got = run_acts(e, t, 8 if gait == "walk" else 1, frames, seat, s)
        on_top += got
    assert "dangle" in on_top and "kick_legs" in on_top, (look, gait)
    assert {"dangle", "kick0", "kick1"} <= frames
    assert all(gaps == {0.0} for gaps in seat.values()), seat  # the seat is the window's top, whatever hangs under it
    # the same picks on the floor, over a longer run: never
    floor: list[str] = []
    for seed in range(1, 25):
        e, s = make(look, gait, seed)
        e.extra_frames = s.extras()
        e.update(1.0)
        floor_frames: set[str] = set()
        _t, got = run_acts(e, 1.0, 8, floor_frames)
        floor += got
        assert not floor_frames & {"dangle", "kick0", "kick1"}
    assert not set(floor) & set(PERCH_ACTS)


def test_a_perch_near_the_screen_bottom_has_no_room_for_the_hem_so_it_is_not_dangled_from() -> None:
    e, s, t = perched("masculine", "walk", 3)
    assert e._hem_room()
    seat = s.metrics(96)[("sit", False)][3]
    hem = max(s.metrics(96)[(f, False)][3] for f in ("dangle", "kick0", "kick1")) - seat
    assert hem > 0
    low = Perch(11, 500, AREA[3] - hem + 1, 1100)
    e2, _s2, t2 = perched("masculine", "walk", 3, low)
    assert not e2._hem_room()
    chosen: list[str] = []
    for _ in range(60):
        e2._perform("rest", t2)
        chosen.append(e2.act)
        e2.state_until = 0
    assert not set(chosen) & set(PERCH_ACTS)


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
def test_the_one_handed_hang_is_drawn_inside_a_long_hang_and_nowhere_else(look: str, gait: str) -> None:
    assert "hang_one_hand" not in dict(e_weights := make(look, gait, 1)[0].mind.weights(0.0, gait, 12, "perch"))
    assert "hang_one_hand" not in dict(e_weights) and "hang_one_hand" not in dict(make(look, gait, 1)[0].mind.weights(0.0, gait, 12, ""))
    seen = hangs = 0
    for seed in range(1, 9):
        e, s = make(look, gait, seed)
        e.extra_frames = s.extras()
        t = 1.0
        e.update(t)
        e._perform("hang", t)
        in_hang = False
        while t < 300:
            t += TICK
            out = e.update(t)
            if out.frame in ("hang_one", "hang_sloth", "hang_feet"):  # L-ui-modernisation-10: the let-go hand is one of three tricks
                assert e.state == "hang" and e.pulling is None and e.swing_to is None and not e.releasing
                assert e.state_until - t >= 9.0 - 1e-6 or e.hang_one_until > t  # never begun in the last nine seconds
                seen += 1
            if e.state == "hang":
                in_hang = True
            elif in_hang:
                hangs += 1
                break
        assert any(e.mind.done.get(a) is not None for a in ("hang_one_hand", "sloth", "hang_by_feet")), seed  # a trick fed the mind: it happened
    assert hangs == 8 and seen > 8 * 20 / TICK / 20, (hangs, seen)  # every hang had its moments of it, a share of the time held


@pytest.mark.parametrize("look", LOOKS)
def test_the_meditation_is_drawn_on_the_floor_with_the_sits_line(look: str) -> None:
    drawn: set[str] = set()
    for seed in range(1, 20):
        e, s = make(look, "walk", seed)
        e.extra_frames = s.extras()
        e.update(1.0)
        e._start_act("meditate", 1.0)
        t = 1.0
        for _ in range(int(14 / TICK)):
            t += TICK
            out = e.update(t)
            if out.frame == "meditate":
                drawn.add("meditate")
                # registered as the sit is: its seat on the floor, within one logical px
                seat = out.y + s.metrics(96)[("sit", out.flip)][3]
                assert abs(AREA[3] - seat) <= 1.0, seat
                assert out.y + s.metrics(96)[("meditate", out.flip)][3] <= AREA[3] + 1.0
    assert drawn == {"meditate"}


@pytest.mark.parametrize("look", LOOKS)
def test_a_look_without_the_pictures_draws_the_pose_each_one_varies(look: str, tmp_path: Path) -> None:
    src = sprites.SpriteSet(look).directory
    (tmp_path / look).mkdir()
    for f in src.glob("*.png"):
        if f.stem not in sprites.EXTRA_FRAMES:
            shutil.copy(f, tmp_path / look / f.name)
    s = sprites.SpriteSet(look, tmp_path)
    assert s.extras() == frozenset() and s.missing() == []  # an older set still runs
    e, _full = make(look, "walk", 3)
    e.extra_frames = s.extras()
    for name, fallback in sprites.EXTRA_FALLBACK.items():
        e._state_frame = lambda _n, n=name: n  # type: ignore[method-assign]
        assert e._frame(1.0) == fallback, name
    e.update(1.0)
    e._perform("hang", 1.0)
    t = 1.0
    frames: set[str] = set()
    while t < 200 and (e.state != "hang" or t < 40):
        t += TICK
        frames.add(e.update(t).frame)
    assert not frames & set(sprites.EXTRA_FRAMES) and e.hang_one_at == float("inf")  # no picture of the one-handed hang: it never begins one


def test_the_new_pictures_are_blended_and_the_captured_looks_leave_them_out() -> None:
    for name in sprites.EXTRA_FRAMES:
        assert name.rstrip("0123456789") in runner.BLENDED, name  # `_blends` strips the digits of kick0 and kick1
    from tessellate.core.overlay import capture

    assert not set(capture.CAPTURED) & set(sprites.EXTRA_FRAMES)  # a companion made from a name has none: `extras()` is empty, the fallbacks draw
    assert set(sprites.EXTRA_FALLBACK) == set(sprites.EXTRA_FRAMES)
    assert all(v in sprites.FRAME_NAMES and v not in sprites.EXTRA_FRAMES for v in sprites.EXTRA_FALLBACK.values())


def test_the_acts_match_the_catalogue_lengths_and_the_long_sits_yield_to_the_sit() -> None:
    import json

    cat = {r["id"]: r for r in json.loads((Path(__file__).resolve().parents[1] / "frontend" / "companion-catalogue.json").read_text())["entries"]}
    for name in ("dangle", "kick_legs", "hang_one_hand", "meditate", "lounge", "rest_head"):
        assert list(bh.ACTIVITIES[name].seconds) == cat[f"act.{name}"]["seconds"], name
        assert cat[f"act.{name}"]["desk"]["s"] == "built", name
    assert bh.ACTIVITIES["dangle"].where == "perch" and bh.ACTIVITIES["kick_legs"].where == "perch"
    assert bh.ACTIVITIES["hang_one_hand"].where == "hang"
    assert {"meditate", "lounge", "rest_head"} <= bh.YIELD_TO_SIT
    assert isinstance(Monitor, type) and eng.IDLE_SIT > 0
