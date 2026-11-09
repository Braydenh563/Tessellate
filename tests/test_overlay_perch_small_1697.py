"""A figure let go on a small window's top stands on it (INBOX 1697, owner on Windows: "I still cant place the
companion to sit on a smaller desktop window"). Before: a top narrower than the figure plus 20 logical px (315 px
for the 275 px figure at 192 dpi) was never a perch, so a drop on a 300 px window fell to the floor, the climb
refused it too, and a narrow top that did perch let the figure's box be clamped off it. Now a top as wide as the
feet (`PERCH_FEET` of the figure) is a perch, the figure's middle stays over it, and a drop and a climb use one
rule. FakeWin32, the owner's screen (2560x1424 at 192 dpi), fixed clock."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import perches  # noqa: E402
from tessellate.core.overlay.win32 import WinInfo  # noqa: E402
from tests.test_overlay_release_1696 import carry_to, owner, settle  # noqa: E402

LEFT = 1000


def win(w: int, h: int, top: int, key: int = 7) -> dict:
    r = (LEFT, top, LEFT + w, top + h)
    return {"rect": r, "outer": r, "frame": (0, 0, 0, 0), "title": "T", "cls": "X"}


@pytest.mark.parametrize("w,h,top", [(300, 200, 700), (200, 150, 700), (150, 120, 800), (400, 300, 700), (300, 200, 1250), (140, 100, 700)])
@pytest.mark.parametrize("fx", [0.1, 0.5, 0.9])
def test_a_drop_on_a_small_top_perches_with_the_middle_over_it(w: int, h: int, top: int, fx: float) -> None:
    r, fake, clock, _ = owner()
    px, py = carry_to(r, clock, int(LEFT + w * fx), top - 20)
    fake.window_list = {7: win(w, h, top)}
    r._on_event("up", px, py)
    e = r.engine
    assert e.state == "rise" and e.target is not None and e.target.key == 7
    settle(r, clock)
    assert e.perch is not None and e.perch.key == 7 and e.state == "stand"
    assert e.y == top - e.size[1]
    cx = e.x + e.size[0] / 2
    assert LEFT <= cx < LEFT + w  # the figure's middle is over the window, not hanging off its side
    r.stop()


def test_a_top_too_narrow_for_the_feet_is_still_no_perch() -> None:
    wins = [WinInfo(7, (LEFT, 700, LEFT + 40, 800), True)]
    assert perches.top_edges(wins, eng.perch_room(275, 2.0)) == []


@pytest.mark.parametrize("w", [150, 200, 300, 400])
def test_the_climb_takes_the_same_tops_the_drop_does(w: int) -> None:
    r, fake, clock, _ = owner()
    e = r.engine
    e.set_windows(perches.top_edges(_wins(w), eng.perch_room(e.size[0], 2.0)), clock.t)
    assert [p.key for p in e._candidates()] == [7]
    r.stop()


def _wins(w: int) -> list[WinInfo]:
    return [WinInfo(7, (LEFT, 700, LEFT + w, 1000), True)]


def test_a_ghost_tool_window_over_a_top_does_not_cover_it() -> None:
    """The owner's log: a layered tool window (Dell's display manager) at top 49 over x 49 to 1649 hid an Explorer
    window's top at 485 as "covered by a tool window"; the figure's drop was refused."""
    from tests._overlay_fake import FakeWin32
    from tessellate.core.overlay import win32 as k

    fake = FakeWin32()
    ghost = {"rect": (49, 49, 1649, 1300), "outer": (49, 49, 1649, 1300), "frame": (0, 0, 0, 0), "title": "", "cls": "HwndWrapper",
             "ex": k.WS_EX_TOOLWINDOW | k.WS_EX_LAYERED | k.WS_EX_NOACTIVATE}
    explorer = {"rect": (180, 485, 2192, 1300), "outer": (180, 485, 2192, 1300), "frame": (0, 0, 0, 0), "title": "D", "cls": "CabinetWClass"}
    fake.window_list = {9: ghost, 7: explorer}
    wins = k.windows(fake, 1, None, [(0, 0, 2560, 1504)])
    assert [w.solid for w in wins if w.key == 9] == [False]
    assert [p.key for p in perches.top_edges(wins, 150)] == [7]
