"""Desk companion: the lower body as a layer (atlascat-1108 C4, INBOX 1696 z: "the lower body doesnt change at all ...
they just stay the exact same like they are frozen in time"). `lower.lie`, `lower.think`, `lower.sad`, `lower.startle`,
`lower.lounge` and `lower.glide` each take the nebula stream's reach, speed and offsets (`behaviour.FLOW_LOWER`); the
engine picks them from what the figure is doing (`Engine._lower_state`). Fixed clock: every time here is passed in."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tests.test_overlay_ride_1670 import make

STATES = ("lie", "think", "sad", "startle", "lounge", "glide", "billow", "coil", "ripple_calm", "flutter", "pool", "hem_kick", "spiral", "heavy")


def put(state: str) -> tuple[eng.Engine, float]:
    """An engine doing what makes `state` the lower body's: returns it and the time it is ready at."""
    e, _ = make()
    t = 1.0
    e.update(t)
    if state == "lie":
        e._enter("sleep", t)
        e.nap_until = 1e9
    elif state == "think":
        e._enter("act", t)
        e.act, e.act_len, e.act_started, e.state_until = "ponder", 1e9, t, 1e9
    elif state == "sad":
        e.ex.over = ("sad", t, 1e9)
    elif state == "startle":
        e._enter("startle", t)
        e.state_until = 1e9
    elif state == "lounge":
        e._enter("sit", t)
        e.state_until = 1e9
        e.update(t + 0.04)  # the first sit picture: the lounge counts from here
        t += bh.LOUNGE_AFTER + 0.5
    elif state == "glide":
        e._enter("walk", t)
        e.state_until = 1e9
    else:
        t = put_c5(e, state, t)
    return e, t


def act(e: eng.Engine, name: str, t: float) -> None:
    e._enter("act", t)
    e.act, e.act_len, e.act_started, e.state_until = name, 1e9, t, 1e9


def put_c5(e: eng.Engine, state: str, t: float) -> float:
    """atlascat-1108 C5: what makes each of the eight new states the lower body's. Returns the time to read at."""
    if state == "billow":
        e._enter("walk", t)
        e.state_until, e.mode = 1e9, "dash"
    elif state == "coil":
        act(e, "groom", t)
    elif state == "hem_kick":
        act(e, "little_dance", t)
    elif state == "spiral":
        act(e, "flip_twirl", t)
    elif state == "flutter":
        e.mind.feel("happy", t)
    elif state == "heavy":
        e.mind.feel("sleepy", t)
        e.mind.event_at = t
    elif state == "pool":
        e._enter("sit", t)
        e.state_until = 1e9
        e.update(t + 0.04)
        t += bh.POOL_AFTER + 0.5
    elif state == "ripple_calm":
        e.update(t + 0.04)
        e.state_at -= bh.RIPPLE_AT + 1.0  # a stand that has lasted 25 s, without 25 s of ticks (the engine would act in them)
    return t


def run(e: eng.Engine, t: float, ticks: int, step: float = 0.04) -> list[eng.Output]:
    out = []
    for _ in range(ticks):
        out.append(e.update(t))
        t += step
    return out


@pytest.mark.parametrize("state", STATES)
def test_the_engine_picks_the_state_from_what_the_figure_is_doing(state: str) -> None:
    e, t = put(state)
    o = e.update(t)
    face = o.face
    assert e._lower_state(t, face) == state, (e.state, face)


def test_a_plain_stand_and_a_short_sit_have_no_state_of_their_own() -> None:
    e, t = make()[0], 1.0
    assert e._lower_state(t, None) == ""
    e._enter("sit", t)
    assert e._lower_state(t, None) == ""
    assert e._lower_state(t + 1.0, None) == ""
    assert e._lower_state(t + bh.LOUNGE_AFTER, None) == "lounge"
    e._enter("sleep", t)
    assert e._lower_state(t, None) == "", "a plain sleep keeps the frame's own row (flow:sleep); only a nap lies"


def test_the_catalogue_states_are_all_in_the_table() -> None:
    for state in STATES:
        assert state in bh.FLOW_LOWER
        reach, speed, tip, rise = bh.FLOW_LOWER[state]
        assert 0.3 <= reach <= 1.0 and 0.3 <= speed <= 2.0
        assert abs(tip) <= 1.0 and abs(rise) <= 1.0, "inside the join's 4 degrees (INBOX 615 and 619)"


@pytest.mark.parametrize("state", STATES)
def test_each_state_changes_the_lower_bodys_sway_and_offset(state: str) -> None:
    frame = "walk3" if state in ("glide", "billow") else "sit" if state in ("lounge", "pool", "coil") else "sleep" if state == "lie" else "stand"
    plain, held = bh.Flow(), bh.Flow()
    t, a, b = 100.0, [], []
    for _ in range(200):  # 8 s at 25 a second: the easing is long done
        a.append(plain.view(t, frame=frame))
        b.append(held.view(t, frame=frame, lower=state))
        t += 0.04
    reach, speed, tip, rise = bh.FLOW_LOWER[state]
    assert (round(held.k_reach, 2), round(held.k_speed, 2)) == (reach, speed)
    assert (round(held.k_tip, 2), round(held.k_rise, 2)) == (tip, rise)
    assert a[-1] != b[-1] and a != b, state
    assert plain.k_tip == 0.0 and plain.k_rise == 0.0


def test_glide_leans_back_from_the_way_it_goes() -> None:
    right, left = bh.Flow(), bh.Flow()
    for k in range(200):
        right.view(100.0 + k * 0.04, frame="walk3", lower="glide", side=-1.0)
        left.view(100.0 + k * 0.04, frame="walk3", lower="glide", side=1.0)
    assert right.k_tip < 0 < left.k_tip


def test_changing_the_state_is_never_a_step() -> None:
    flow, t, reads = bh.Flow(), 10.0, []
    for k in range(500):
        reads.append(flow.view(t, frame="stand", lower="" if k < 250 else "startle"))
        t += 0.04
    jumps = [max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(reads, reads[1:])]
    assert max(jumps[250:300]) <= max(jumps[:240]) + 2, (max(jumps[250:300]), max(jumps[:240]))


@pytest.mark.parametrize("state", ("", *STATES))
def test_the_lower_layer_is_never_identical_across_ten_ticks_at_rest(state: str) -> None:
    e, t = put(state) if state else (make()[0], 1.0)
    views = []
    for _ in range(40):  # the rest tick is 170 ms: 40 of them are 7 s, before a trip may start
        o = e.update(t)
        views.append(o.flow)
        t += max(0.03, (o.wake_ms or 1000) / 1000.0)
    assert all(v is not None for v in views)
    for k in range(0, 40 - 10, 5):
        window = views[k:k + 10]
        assert len(set(window)) > 1, (state, k, "frozen for ten ticks")


def test_a_sad_reaction_is_read_from_the_same_signal_the_startle_is() -> None:
    # `ex.over` is the reaction's face: sad is picked from it with no face passed in, as a startle is.
    e, t = put("sad")
    assert e._lower_state(t, None) == "sad"
    e2, t2 = put("sad")
    e2.ex.over = ("worried", t2, 1e9)
    assert e2._lower_state(t2, None) == "startle"
    e2.ex.over = None
    assert e2._lower_state(t2, None) == ""
