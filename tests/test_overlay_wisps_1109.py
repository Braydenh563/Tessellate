"""The desk's lower body and nebula streams move like the in-app ones (INBOX 1683 a, 1696 w, owner: "little organic or
natural subtle movement with the lower body wisps and the nebula streams"). Measured on the engine and the sprites at
96 dpi, seeded, fixed clock (never the real one); real Windows is not verified. The hem is the bottom quarter of the
drawn box: it must breathe with the body (a wave runs down it a beat late), never sit still for 2 s, and trail a stop."""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tests import overlay_pace_sim as sim  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402


def hem(s, out):
    """The hem (the lowest two fifths of the canvas) of what the runner would draw, as an int array."""
    p = s.posed(out.frame, 96, out.flip, out.pose or eng.bh.NEUTRAL, out.flow) if out.pose or out.flow else s.frame(out.frame, 96, out.flip)
    if out.tail:
        p = s.tailed(p, out.frame, 96, out.flip, out.tail)
    a = np.frombuffer(p.bgra, np.uint8).reshape(p.height, p.width, 4)
    left, _top, right, _bottom = p.box
    return a[p.height * 3 // 5:, left:right].astype(np.int16)  # fixed canvas rows: the box's own edges move with the breath


def rest_run(seed: int, secs: float, sit: bool = True):
    """The hem at every tick of a seeded rest (from 30 s in, when it has sat down) with the breath's swell."""
    e, s = make("masculine", "float", seed)
    e.presence, e.wave_ready = False, math.inf  # the plain companion at rest: no spell, no wave at the pointer
    timer = sim.paced_host()
    t, out, rec = 0.0, e.update(0.0), []
    while t < 30.0:
        t = timer(t, out.wake_ms or 16)
        out = e.update(t)
    if sit:
        e._enter("sit", t)
        out = e.update(t)
    while len(rec) == 0 or t - rec[0][0] < secs:
        t = timer(t, out.wake_ms or 16)
        out = e.update(t)
        if e.state not in ("sit", "stand"):
            continue
        life = e._rest_life()
        swell = (1.0 - math.cos(2 * math.pi * t / life[0])) / 2.0 if life else None
        rec.append((t, e.state, hem(s, out), swell))
    return rec


def rows_centre(a) -> float:
    al = a[..., 3].astype(float)
    return float((al.sum(1) * np.arange(al.shape[0])).sum() / max(1.0, al.sum()))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_hem_rises_and_settles_with_the_breath_at_rest(seed: int, monkeypatch) -> None:
    # The same seeded rest drawn twice, with the breath term off and on: the difference is the term alone (the tail and the
    # ambient sway are the same in both), and it must follow the chest's swell, the hem lifting a beat after it.
    monkeypatch.setattr(eng.wisps, "phase", lambda *_a: None)
    off = [r for r in rest_run(seed, 40.0) if r[1] == "sit" and r[3] is not None]
    monkeypatch.undo()
    on = [r for r in rest_run(seed, 40.0) if r[1] == "sit" and r[3] is not None]
    # A sample floor for the correlation, not a frame-rate bar: life2b-1109 skips idle frame edges under a look or
    # blink (the owner's 500 rest ceiling), so seed 1's sit holds exactly 60 frames; the two bars below are unchanged.
    assert len(on) == len(off) >= 50
    diff = np.array([rows_centre(a[2]) - rows_centre(b[2]) for a, b in zip(on, off)])
    swell = np.array([r[3] for r in on])
    corr = float(np.corrcoef(diff, swell)[0, 1])
    # before: no term, so no difference at all (the hem and the breath were unrelated: |r| 0.0 to 0.24 on the whole hem)
    assert corr <= -0.4, corr
    assert diff.max() - diff.min() >= 0.15, diff.max() - diff.min()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_hem_is_never_the_same_picture_for_two_seconds_at_rest(seed: int) -> None:
    rec = rest_run(seed, 30.0)
    start = 0
    longest = 0.0
    for i in range(1, len(rec)):
        if rec[i][2].shape != rec[start][2].shape or not np.array_equal(rec[i][2], rec[start][2]):
            start = i
        longest = max(longest, rec[i][0] - rec[start][0])
    assert longest < 2.0, longest


def test_a_stop_throws_the_wisps_on_past_the_body_and_they_settle() -> None:
    flow = bh.Flow()
    mean = []
    for k in range(360):
        flow.step(1 / 60, 220.0 if k < 120 else 0.0, 0.0)
        mean.append(sum(p[0] for p in flow.pos) / bh.FLOW_BANDS)
    assert min(mean[:120]) <= -3.5  # leant back while it went
    assert max(mean[120:]) >= 1.5  # overshoots the other way after the stop
    assert all(abs(m) < 0.3 for m in mean[300:])  # and has settled within 3 s


def test_the_breath_term_is_small_integers_and_does_not_add_a_wake() -> None:
    flow = bh.Flow()
    a = flow.view(10.0, frame="sit", breath=0.25)
    assert all(isinstance(v, int) for v in a) and len(a) == bh.FLOW_BANDS * 5
    assert a == bh.Flow().view(10.0, frame="sit", breath=0.25)  # a pure function of the clock and the phase
    assert a != bh.Flow().view(10.0, frame="sit", breath=0.75)
