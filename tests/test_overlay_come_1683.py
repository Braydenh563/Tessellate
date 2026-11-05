"""INBOX 1683 (t): "Come here" means follow me. The menu is opened on the figure, so it waits for the pointer to leave,
then comes to it wherever it is (the ground, or a window top the pointer is high over), reacts, keeps company, and a
second "Come here" stops it. Fixed clock, seeded randomness."""
from __future__ import annotations

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Perch
from tests.test_overlay_moves import make

T0 = 10.0


def run(e, t, seconds, pointer, dt=0.05):
    end = t + seconds
    while t < end:
        t += dt
        e.update(t, pointer=pointer)
    return t


def start(seed=5, **kw):
    e = make(seed=seed, **kw)
    e.roam_windows = True
    e.update(T0, pointer=(860, 950))
    e.x = 800.0
    return e


def arrive_time(e, t, pointer, limit=30.0, ok=None):
    t0 = t
    while t - t0 < limit:
        t += 0.05
        e.update(t, pointer=pointer)
        if ok(e):
            return t - t0
    return None


def test_pointer_beside_the_figure_then_moved_to_the_middle_it_comes() -> None:
    e = start()
    assert e.command("come", T0 + 0.1)
    t = run(e, T0 + 0.1, 0.3, (860, 950))  # still beside it: waiting
    assert e.come["phase"] == "wait"
    far = (1300, 600)
    secs = arrive_time(e, t, far, ok=lambda e: e.come and e.come["phase"] != "go")
    assert secs is not None and secs < 12.0
    gap = abs((e.x + e.size[0] / 2) - far[0])
    assert gap <= eng.COME_GAP * e._scale() + e.size[0] / 2 + 5  # the middle third was allowed
    print(f"arrived in {secs:.2f}s, {gap:.0f}px from the pointer")


def test_with_the_pointer_still_it_follows_after_the_wait() -> None:
    e = start()
    e.command("come", T0)
    run(e, T0, eng.COME_WAIT + 0.2, (860, 950))
    assert e.come["phase"] in ("go", "stay")


def test_pointer_over_a_window_top_it_ends_perched_there() -> None:
    e = start(seed=2)
    win = Perch(11, 1000, 600, 1500)
    e.set_windows([win], 0.0)
    e.command("come", T0)
    t = run(e, T0, 0.3, (860, 950))
    secs = arrive_time(e, t, (1250, 560), limit=40.0, ok=lambda e: e.perch is not None and e.perch.key == 11)
    assert secs is not None
    print(f"perched in {secs:.2f}s")
    assert e.come is not None


def test_company_ends_after_come_for_and_a_second_come_stops_it() -> None:
    e = start()
    e.command("come", T0)
    t = run(e, T0, 8.0, (1300, 600))
    assert e.come is not None
    assert e.command("come", t)
    assert e.come is None
    x = e.x
    run(e, t, 3.0, (200, 600))
    assert abs(e.x - x) < 400  # no longer tracking the pointer
    e2 = start()
    e2.command("come", T0)
    run(e2, T0, eng.COME_FOR * 3 + 20, (1300, 600))
    assert e2.come is None


def test_it_retargets_when_the_pointer_moves_far() -> None:
    e = start()
    e.command("come", T0)
    t = run(e, T0, 12.0, (1300, 600))
    assert e.come is not None
    secs = arrive_time(e, t, (200, 600), ok=lambda e: e.come and e.come["phase"] != "go" and e.x < 500 and e.state != "walk")
    assert secs is not None
