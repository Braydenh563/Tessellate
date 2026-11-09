"""INBOX 1699 (the owner, 2026-11-09, Windows): "it is just hanging in mid air". A hang lasts 60 to 300 s and the window list was
not read while it hung (`Runner._wants_scan` knew the stand, a perch, a tuck, a carry, not a hang), so a window closed or
moved from under the hands left the figure holding the air. Fixed clock, the fake win32."""

from __future__ import annotations

import pytest

from tests.test_overlay_roam_runner import due, started, tick


def _hanging():
    pytest.importorskip("PIL")
    r, fake, clock, _ = started()
    fake.window_list = {5: {"rect": (400, 300, 1300, 800), "title": "Notes"}}
    due(r, clock)
    tick(r, clock, 0.1, 25)
    e = r.engine
    p = next(q for q in e.windows if q.key == 5)
    e.perch = None
    e.x = (p.left + p.right) / 2 - e.size[0] / 2
    e.y = e._grip(p) - e._lift()
    e.hang_on = p
    e._enter("hang", clock.t)
    e.state_until = clock.t + 200.0
    return r, fake, clock, e


@pytest.mark.parametrize("change", ["closes", "minimises", "moves"])
def test_a_window_taken_from_under_a_hang_lets_it_go_within_a_second(change: str) -> None:
    r, fake, clock, e = _hanging()
    assert r._wants_scan(clock.t), "a hang rides its window: the list is read while it hangs"
    if change == "closes":
        del fake.window_list[5]
    elif change == "minimises":
        fake.window_list[5]["iconic"] = True
    else:
        fake.window_list[5]["rect"] = (400, 300 + 200, 1300, 800)
    tick(r, clock, 0.1, 12)
    assert e.state != "hang" or e.hang_on is not None, (e.state, e.hang_on)
    assert not (e.state == "hang" and e.hang_on is None), "never holding the air"
    r.stop()


def test_a_hang_whose_window_stays_keeps_hanging() -> None:
    r, fake, clock, e = _hanging()
    tick(r, clock, 0.1, 30)
    assert e.state == "hang" and e.hang_on is not None and e.hang_on.key == 5
    r.stop()
