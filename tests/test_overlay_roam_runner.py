"""The runner's half of roam and carry, on a fake `win32`: window tops read at most
once a second and only when useful, skipped windows, the reminder hand-off, and
the dpi under a point. Windows itself cannot run here."""

from __future__ import annotations

import os
from typing import Any

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import perches  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tessellate.core.overlay import runner  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402
from tests.test_overlay_runner import make, wait_for  # noqa: E402

TOOL = k.WS_EX_TOOLWINDOW


def started(fake: FakeWin32 | None = None, **kw: Any):
    r, fake, clock, clicks, settled = make(fake, reduced=kw.pop("reduced", False), **kw)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    r.paused = True  # the test drives ticks itself
    r._resume = False  # the first tick after a show would reset the engine's idle clock
    return r, fake, clock, clicks


def scans(fake: FakeWin32) -> int:
    return fake.names("user32").count("EnumWindows")


def tick(r, clock, dt: float = 0.1, n: int = 1, pointer=(900, 300)) -> None:
    for _ in range(n):
        clock.t += dt
        r._system("tick", clock.t, pointer)


def due(r, clock) -> None:
    """Past the first trip's delay, standing: a trip (to a window) could come now."""
    clock.t = r.engine.trip_ready + 5
    r.engine.last_active = clock.t


def test_window_tops_are_read_at_most_once_a_second_and_given_to_the_engine() -> None:
    r, fake, clock, _ = started()
    fake.window_list = {5: {"rect": (300, 400, 1100, 900), "title": "Notes"}}
    due(r, clock)
    before = scans(fake)
    tick(r, clock, 0.1, 25)  # 2.5 s of ticks
    assert 2 <= scans(fake) - before <= 3
    assert r.engine.windows == [eng.Perch(5, 300, 400, 1100)]
    r.stop()


def test_skipped_windows_are_never_perches_but_the_ones_above_still_hide_a_top() -> None:
    r, fake, clock, _ = started()
    fake.window_list = {
        2: {"rect": (200, 300, 900, 800), "title": "Tool", "ex": TOOL},
        3: {"rect": (200, 300, 900, 800), "title": "Own", "pid": os.getpid()},
        4: {"rect": (200, 300, 900, 800), "title": "Max", "zoomed": True},
        5: {"rect": (200, 300, 900, 800), "title": "Min", "iconic": True},
        6: {"rect": (200, 300, 900, 800), "title": "Away", "cloaked": True},
        7: {"rect": (200, 300, 900, 800), "title": "", },
        8: {"rect": (200, 300, 900, 800), "title": "Hidden", "visible": False},
        9: {"rect": (200, 300, 900, 800), "title": "Clickthrough", "ex": k.WS_EX_TRANSPARENT | k.WS_EX_LAYERED},
        10: {"rect": (1000, 500, 1700, 900), "title": "Good"},
        1: {"rect": (0, 0, 1920, 1040), "title": "Full", "ex": 0},  # fills the work area, at the bottom
    }
    wins = k.windows(fake, os.getpid(), None, [(0, 0, 1920, 1040)])
    assert {w.key: w.perch for w in wins} == {1: False, 2: False, 3: False, 4: False, 7: False, 10: True}
    assert perches.top_edges(wins, 120) == [eng.Perch(10, 1000, 500, 1700)]  # the visible ones above hide nothing of it
    r.stop()


def test_a_window_above_covers_part_of_the_top_edge_under_it() -> None:
    wins = [
        k.WinInfo(1, (500, 300, 700, 900), True),   # on top, covers x 500..700 at y 300..900
        k.WinInfo(2, (300, 500, 1300, 900), True),  # its top (y 500) is cut by window 1
    ]
    got = {p.key: p for p in perches.top_edges(wins, 120)}
    assert got[2] == eng.Perch(2, 700, 500, 1300)  # the wider side stays
    assert perches.top_edges([wins[0], k.WinInfo(2, (400, 500, 720, 900), True)], 120) == [eng.Perch(1, 500, 300, 700)]  # nothing wide enough is left


def test_the_overlays_own_window_is_ignored() -> None:
    fake = FakeWin32()
    fake.window_list = {1234: {"rect": (0, 100, 300, 400), "title": "overlay"}, 9: {"rect": (400, 100, 900, 400), "title": "w"}}
    assert [w.key for w in k.windows(fake, 1, 1234, [(0, 0, 1920, 1040)])] == [9]


@pytest.mark.parametrize("why", ["sitting", "asleep", "typing", "still", "switched_off", "not_due"])
def test_nothing_is_read_when_a_climb_cannot_happen(why: str) -> None:
    kw = {"reduced": True} if why == "still" else {}
    r, fake, clock, _ = started(**kw)
    fake.window_list = {5: {"rect": (300, 400, 1100, 900), "title": "Notes"}}
    if why != "not_due":
        due(r, clock)
    minute = 120
    if why == "not_due":
        minute = 30  # 15 s: the first climb is not near yet
    if why == "sitting":
        r.engine.last_active = clock.t - 700  # long untouched: it stays sat down
        r.engine._enter("sit", clock.t)
    elif why == "asleep":
        r.engine._enter("sleep", clock.t)
    elif why == "typing":
        fake.last_input = (10_000, 9_500)  # input half a second ago, all minute
    elif why == "switched_off":
        r.set_roam(False)
    before = len(fake.calls)
    tick(r, clock, 0.5, minute)
    assert scans(fake) == 0
    calls = [fn for _d, fn, _a in fake.calls[before:]]
    assert not any(fn in ("EnumWindows", "IsWindowVisible") for fn in calls)
    #: 1670 13:22Z added one read while typing: the foreground window's frame, for the text band an app
    #: with no caret leaves bare. It is not a climb read, and it is kept per window, so a typing minute
    #: costs at most one frame read every runner.ZONE_EVERY s; every other case still reads none.
    frames = calls.count("DwmGetWindowAttribute")
    assert frames <= (1 + int(minute * 0.5 // runner.ZONE_EVERY) if why == "typing" else 0)
    r.stop()


def test_an_idle_minute_costs_at_most_one_scan_a_second_and_its_window_calls() -> None:
    r, fake, clock, _ = started()
    fake.window_list = {i: {"rect": (100 * i, 300, 100 * i + 600, 800), "title": f"w{i}"} for i in range(1, 8)}
    due(r, clock)
    r.engine.last_active = 1e9  # never idle long enough to sit: it stays standing
    r.engine.next_ambient = 1e9
    r.engine.state_until = 1e9
    r.engine.trip_ready = clock.t  # due, but nothing picks it: the test only counts reads
    r.engine.relocate_at = None  # (home is in the middle third: its move to an edge is not an idle minute)
    r.engine.eager_ready = 1e9  # seven windows are all new: going to the first within seconds (INBOX 1692 n) is not an idle minute
    r.engine.big_ready = 1e9
    start = len(fake.calls)
    for _ in range(600):  # ten ticks a second for a minute
        tick(r, clock, 0.1)
    window_calls = sum(1 for _d, fn, _a in fake.calls[start:] if fn in ("EnumWindows", "IsWindowVisible", "IsIconic", "IsZoomed", "GetWindowLongW", "GetWindowTextLengthW", "GetWindowThreadProcessId", "DwmGetWindowAttribute"))
    assert scans(fake) <= 61
    assert window_calls <= 61 * (1 + 7 * 9)  # 7 windows, nine calls each at most
    r.stop()


def test_a_wanted_scan_caps_the_wake_so_the_next_read_is_on_time() -> None:
    r, fake, clock, _ = started()
    due(r, clock)
    r.engine.next_ambient = 1e9  # nothing else is picked: it stays standing
    r.engine.relocate_at = None  # (its home is in the middle third: the move to an edge is not this test)
    r.engine.state_until = 1e9
    r.engine.big_ready = 1e9
    tick(r, clock, 0.1)
    assert r.engine.state == "stand"
    assert r._scan_wake(8000) <= 1000
    r.set_roam(False)
    assert r._scan_wake(8000) == 8000


def test_a_reminder_is_queued_for_the_engine_and_a_click_on_its_card_comes_back() -> None:
    got: list[Any] = []
    r, fake, clock, _ = started(on_card=got.append)
    r.bring_card("r9")
    tick(r, clock, 0.1, 3)
    assert r.engine.card == "r9"
    for _ in range(2000):
        tick(r, clock, 0.033)
        if r.engine.state == "card":
            break
    assert r.engine.state == "card"
    px, py = int(r.engine.x + 20), int(r.engine.y + 20)
    r._apply(r.engine.update(clock.t + 0.1, (px, py), ("down", px, py)))
    r._apply(r.engine.update(clock.t + 0.2, (px, py), ("up", px, py)))
    assert got == ["r9"]
    r.stop()


def test_a_card_waiting_while_the_window_is_hidden_is_not_lost() -> None:
    r, fake, clock, _ = started()
    r.visible = False
    r.bring_card("later")
    tick(r, clock, 0.1, 3)
    assert r.engine.card is None and list(r._cards) == ["later"]
    r.visible = True
    tick(r, clock, 0.1, 2)
    assert r.engine.card == "later"
    r.stop()


def test_the_dpi_under_a_point_is_the_monitors_even_left_of_the_primary() -> None:
    fake = FakeWin32()
    fake.monitor_list = [((0, 0, 1920, 1040), 96), ((-1920, 0, 0, 1000), 144)]
    r, *_ = make(fake)
    assert r.start()
    assert r.dpi_at(500, 500) == 96
    assert r.dpi_at(-500, 500) == 144
    assert r.dpi_at(-5000, 500) == 144  # off every monitor: the nearest
    assert k.dpi_at_point(fake, 2500, 100) == 96
    r.stop()
