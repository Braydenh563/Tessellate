"""INBOX 1719 b (the owner: "can the in-app and desktop companion have more life and biological design to them?"):
the body's own rhythms from one table both companions read (`vitals` in `frontend/companion-catalogue.json`).

Blinks by mood and tiredness: before this, the desk blinked 16.5 times a minute for 0.28 s whatever its mood (seeded
probe, 10 min standing, seeds 1 to 3, `life-1109.md`). Breath by exertion and mood: a sit after a walk breathed at the
same 4.8 s as a sit after a stand. Engine and fakes on a fixed clock; nothing here runs on Windows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import vitals
from tests.overlay_sim_1670 import home_at_edge
from tests.test_overlay_ride_1670 import make

ROOT = Path(__file__).resolve().parents[1]
MOODS = {
    "happy": ({"rest": 0.2, "curiosity": 0.2, "play": 0.7, "novelty": 0.0}, ""),
    "sleepy": ({"rest": 0.95, "curiosity": 0.2, "play": 0.2, "novelty": 0.0}, ""),
    "curious": ({"rest": 0.2, "curiosity": 0.9, "play": 0.2, "novelty": 0.0}, ""),
    "startled": ({"rest": 0.2, "curiosity": 0.2, "play": 0.2, "novelty": 0.0}, "startled"),
}


def _still(seed: int):
    e, _s = make("masculine", "float", seed)
    e.presence = False
    home_at_edge(e)
    e.big_ready = e.trip_ready = e.climb_ready = e.ex.act_ready = float("inf")
    e.update(0.0)
    e.state_until = float("inf")
    return e


def blinks(mood: str, seed: int, secs: float = 600.0) -> tuple[float, float]:
    """Blinks a minute and the mean blink length, standing `secs` with the mood held."""
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        e = _still(seed)
        needs, event = MOODS[mood]
        n, total, t, was = 0, 0.0, 0.0, False
        while t < secs:
            e.mind.needs.update(needs)
            e.mind.event, e.mind.event_at = event, t - 1.0
            out = e.update(t)
            on = bool(e.flash and e.flash[0] == "blink")
            if on and not was:
                n += 1
                total += e.flash[1] - e.blink_at
            was = on
            t += min(max(0.016, (out.wake_ms or 1000) / 1000.0), 0.25)
        assert e.mind.mood(t, e.hour) == mood
        return n / (secs / 60.0), total / max(1, n)
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved


def test_the_table_is_the_catalogues():
    """The app reads the same numbers (`atlas-vitals.js`): the catalogue's `vitals` is the desk's built-in table."""
    doc = json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))
    assert doc["vitals"] == vitals.DEFAULTS
    assert set(vitals.DEFAULTS["blink"]["mood"]) <= set(doc["moods"])
    assert set(vitals.DEFAULTS["breath"]["mood"]) <= set(doc["moods"])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_blinks_follow_the_mood_and_the_tiredness(seed: int):
    got = {m: blinks(m, seed) for m in MOODS}
    rate, length = got["happy"]
    assert 12.0 <= rate <= 21.0 and abs(length - eng.BLINK_FOR) < 1e-6, got  # a person's 15 or so a minute
    assert got["sleepy"][0] >= 1.25 * rate and got["sleepy"][1] >= 1.6 * length, got  # heavy lids, more often
    assert got["curious"][0] <= 0.8 * rate and got["startled"][0] <= 0.8 * rate, got  # a held gaze
    assert got["startled"][1] < length, got  # a quick one


def test_a_long_blink_keeps_its_phases():
    """The lid's steps (light, shut, light) keep their shares of a longer blink: none is skipped."""
    e = _still(1)
    e.blink_for = eng.BLINK_FOR * 1.7
    e.flash, e.blink_at = ("blink", 10.0 + e.blink_for), 10.0
    steps = [e._blink_step(10.0 + e.blink_for * u / 20)[0] for u in range(20)]
    assert [s for i, s in enumerate(steps) if i == 0 or s != steps[i - 1]] == [2, 0, 2]


def _sit_after(before: str, seed: int = 1, wait: float = 0.0) -> float:
    e = _still(seed)
    e.mind.needs.update(MOODS["happy"][0])
    e._enter(before, 1.0)
    e._enter("stand", 2.0)  # it stops, then sits `wait` s later
    e._enter("sit", 2.0 + wait)
    return e._rest_life()[0]


def test_a_sit_after_a_walk_breathes_quicker_and_eases_back():
    calm = _sit_after("stand")
    assert abs(calm - eng.REST_LIFE["sit"][0] * vitals.breath("happy", 0.0)) < 1e-9
    for state in ("walk", "hop", "held", "fall"):
        assert calm / _sit_after(state) >= 1.3, state  # was 1.0: every sit breathed at 4.8 s
    assert calm / _sit_after("walk", wait=60.0) < 1.05  # a minute on, it has its breath back


def test_asleep_and_sleepy_breathe_slower_and_startled_quicker():
    assert vitals.breath("sleepy", 0.0) > 1.1 > 1.0 > vitals.breath("startled", 0.0)
    assert vitals.exertion(0.0) == 1.0 and vitals.exertion(vitals.DEFAULTS["breath"]["half_s"]) == pytest.approx(0.5)


def test_a_broken_table_is_the_default(monkeypatch):
    from tessellate.core.overlay import catalogue

    monkeypatch.setattr(catalogue, "load", lambda: {"vitals": {"blink": "nonsense", "breath": {"mood": 3}}})
    assert vitals.blink("sleepy", 0.0) == tuple(vitals.DEFAULTS["blink"]["mood"]["sleepy"])
    assert vitals.breath("sleepy", 0.0) == 1.0
