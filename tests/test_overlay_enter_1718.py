"""The first show arrives (INBOX 1718 a, owner: "right now the desktop companion just appears when I load up or first
minimise the app, can it transition in somehow"): a portal or a puff plays only its way in, an edge lets it in, a walker
may drop in and land; never the plain figure in the first frame. Seeded, fixed clock; the first visible frames are read."""

from __future__ import annotations

import random

from tessellate.core.overlay.engine import Engine, Monitor

ONE = [Monitor((0, 0, 1920, 1040), 96)]


def make(seed: int, **kw) -> Engine:
    e = Engine((100, 120), ONE, rng=random.Random(seed), home=(800, 920), **kw)
    e.update(1.0)
    return e


def test_every_seeded_entrance_is_an_effect_a_fade_or_a_drop_never_a_plain_stand() -> None:
    seen = set()
    for seed in range(40):
        e = make(seed)
        pick = e.enter_scene(2.0)
        seen.add(pick)
        assert pick in ("portal", "puff", "edge", "drop"), seed
        state_before = e.state
        out = e.update(2.0)  # the first visible frame
        if pick == "drop":
            assert state_before == "fall" and out.y < 0, (seed, out.y)
        else:
            assert state_before == "warp" and e.warp is not None, (seed, pick)
            assert out.alpha < 1.0 or out.fx is not None or out.clip is not None, (seed, pick, out)
    assert seen == {"portal", "puff", "edge", "drop"}


def test_it_is_over_within_four_seconds() -> None:
    for seed in range(12):
        e = make(seed)
        e.enter_scene(2.0)
        t = 2.0
        while t < 6.0 and e.state in ("warp", "fall", "fly", "land", "emerge"):
            t += 0.033
            e.update(t)
        assert e.state not in ("warp", "fall", "fly"), (seed, e.state, t)


def test_a_floater_never_drops_and_reduced_motion_stays_put() -> None:
    for seed in range(30):
        assert make(seed, gait="float").enter_scene(2.0) != "drop"
    assert make(1, reduced=True).enter_scene(2.0) == ""


def test_the_runner_enters_only_when_the_coordinator_says_it_is_the_first_show() -> None:
    from tests.test_overlay_runner import make as make_runner

    r, *_ = make_runner()
    assert r.enter is False and r.start() and r.entrance == ""
    r.stop()
    r, *_ = make_runner()
    r.enter = True
    assert r.start() and r.entrance in ("portal", "puff", "edge", "drop")
    r.stop()


def test_the_coordinator_hands_the_first_runner_the_flag_and_the_restart_not() -> None:
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src" / "tessellate" / "core" / "desk_companion.py").read_text(encoding="utf-8")
    assert "runner.enter = not self._entered" in src and "self._entered = self._entered or started" in src
