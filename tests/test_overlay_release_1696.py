"""A figure let go over a window's top stands on it (INBOX 1696 b, owner: "I tried to drag the desktop companion
onto the top of my file explorer window but it just fell and didnt register at all"). Before: no release ever
landed on a window top (a drop or a slow throw fell or floated to the taskbar; only a title bar near the head was
taken hold of), the edge came from the last periodic scan (up to a second old), and a window DWM gave an empty frame
was counted "no frame" and never listed. Now the release reads the windows afresh, the feet within reach of a top
edge settle onto it, and the log says what each window near the feet counted as. FakeWin32, owner's screen, fixed clock."""

from __future__ import annotations

import logging
from collections import Counter

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402
from tests.test_overlay_roam_runner import scans, started  # noqa: E402

#: An Explorer window, not maximised, whose DWM frame comes back empty (it draws its own): the rectangle is read
#: from GetWindowRect instead.
EXPLORER = {"rect": (900, 700, 2000, 1300), "outer": (900, 700, 2000, 1300), "frame": (0, 0, 0, 0), "title": "Downloads", "cls": "CabinetWClass"}
LOG = "tessellate.core.overlay.runner"


def owner():
    fake = FakeWin32()
    fake.monitor_list = [((0, 0, 2560, 1424), 192)]
    return started(fake, home=(1200, 1400), look="feminine")


def carry_to(r, clock, feet_x: int, feet_y: int) -> tuple[int, int]:
    """Press on the figure, carry it slowly until its feet are near (feet_x, feet_y); returns the pointer."""
    e = r.engine
    w, h = e.size
    r.paused = False
    gx, gy = int(e.x + w / 2), int(e.y + h / 2)
    r._on_event("down", gx, gy)
    tx, ty = feet_x, feet_y - h // 2
    for i in range(1, 41):  # half a second of carrying, slow enough not to be a throw
        clock.t += 0.0125
        r._on_event("move", round(gx + (tx - gx) * i / 40), round(gy + (ty - gy) * i / 40))
    assert e.state == "held"
    for _ in range(12):  # held still a moment before the release
        clock.t += 0.0125
        r._on_event("move", tx, ty)
    return tx, ty


def settle(r, clock, seconds: float = 6.0) -> None:
    r.paused = True
    for _ in range(int(seconds / 0.033)):
        clock.t += 0.033
        r._apply(r.engine.update(clock.t))
        if r.engine.perch is not None and r.engine.state == "stand":
            return


def test_the_frame_dwm_leaves_empty_is_read_from_the_window_rectangle() -> None:
    fake = FakeWin32()
    fake.window_list = {7: dict(EXPLORER)}
    tally: Counter = Counter()
    wins = k.windows(fake, 1, None, [(0, 0, 2560, 1424)], tally)
    assert [(w.rect, w.perch) for w in wins] == [((900, 700, 2000, 1300), True)]
    assert tally == {"perch": 1}  # before: {"no frame": 1}, and nothing listed


@pytest.mark.parametrize("above", [60, -40])
def test_let_go_with_the_feet_near_a_window_top_it_stands_on_it(caplog, above: int) -> None:
    caplog.set_level(logging.INFO, logger=LOG)
    r, fake, clock, _ = owner()
    px, py = carry_to(r, clock, 1400, 700 - above)
    fake.window_list = {7: dict(EXPLORER)}  # opened since the last periodic scan: only a fresh read sees it
    before = scans(fake)
    r._on_event("up", px, py)
    assert scans(fake) == before + 1  # read at the release
    e = r.engine
    assert e.state == "rise" and e.target is not None and e.target.key == 7
    settle(r, clock)
    assert e.perch is not None and e.perch.key == 7 and e.state == "stand"
    assert e.y == 700 - e.size[1]  # on its top, not hovering above it or under it
    text = caplog.text
    assert "a CabinetWClass window, top 700, x 900 to 2000, counted as perch, its top is a place to stand" in text
    assert "let go over a window top" in text and "Downloads" not in text  # a class, never a title
    r.stop()


def test_a_window_that_is_no_place_to_stand_is_named_with_its_reason(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOG)
    r, fake, clock, _ = owner()
    px, py = carry_to(r, clock, 1400, 660)
    fake.window_list = {7: dict(EXPLORER, ex=k.WS_EX_TOOLWINDOW, cls="ToolPane")}
    r._on_event("up", px, py)
    assert r.engine.target is None and r.engine.state in ("fly", "fall")  # nothing to stand on: it goes down
    assert "a ToolPane window, top 700, x 900 to 2000, counted as tool window" in caplog.text
    assert "let go with no window top under the figure" in caplog.text
    r.stop()


def test_far_above_a_top_it_still_goes_down(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOG)
    r, fake, clock, _ = owner()
    fake.window_list = {7: dict(EXPLORER)}
    px, py = carry_to(r, clock, 1400, 700 - 250)  # higher and the head is near the screen top: it hangs there
    r._on_event("up", px, py)
    e = r.engine
    assert e.target is None and e.state == "fly" and e.perch is None
    assert "above a window top: out of reach" in caplog.text
    r.stop()


def test_a_throw_over_a_top_is_still_a_throw() -> None:
    r, fake, clock, _ = owner()
    e = r.engine
    w, h = e.size
    fake.window_list = {7: dict(EXPLORER)}
    r.paused = False
    gx, gy = int(e.x + w / 2), int(e.y + h / 2)
    r._on_event("down", gx, gy)
    for i in range(1, 9):  # 2400 px/s sideways
        clock.t += 1 / 60
        r._on_event("move", gx + i * 40, gy)
    clock.t += 1 / 60
    r._on_event("up", gx + 9 * 40, gy)
    assert e.state == "fly" and e.target is None
    assert eng.PERCH_THROW * eng.THROW_MIN * 2 < 2400  # the scale at dpi 192 is 2
    r.stop()
