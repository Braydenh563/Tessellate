"""The desk size handle shows the diagonal resize cursor when the pointer is over it, the same diagonal as the
app's grip (owner 2026-11-07: "the mouse cursor doesnt change when govering over it"): NESW standing (top
right), NWSE hanging (bottom right), back to the arrow off it. Fake `win32`, fixed clock."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import win32 as k  # noqa: E402
from tests.test_overlay_roam_runner import started, tick  # noqa: E402
from tests.test_overlay_size_1107 import show_handle, stand  # noqa: E402


def _cursors(fake) -> list[int]:
    return [int(args[0]) for d, fn, args in fake.calls if fn == "SetCursor"]


def _loaded(fake) -> list[int]:
    return [int(args[1]) for d, fn, args in fake.calls if fn == "LoadCursorW" and args[1] is not None]


def _loaded_soon(fake, idc: int, within: float = 2.0, until=None) -> list[int]:
    """The host loads the cursor on its own thread when the runner's command reaches it, so on a loaded
    machine the load can trail the tick (CI on PR 216, 3.12: only the class arrow loaded yet). Polled on
    the real clock, which paces only this wait; the engine's clock stays the fixed one."""
    import time

    end = time.monotonic() + within
    ready = until or (lambda: idc in _loaded(fake))
    while not ready() and time.monotonic() < end:
        time.sleep(0.01)
    return _loaded(fake)


def test_over_the_handle_the_cursor_is_the_diagonal_and_off_it_the_arrow() -> None:
    r, fake, clock, _ = started()
    stand(r, clock)
    rect = show_handle(r, clock)
    assert rect is not None
    hx, hy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    r._on_event("move", hx, hy)
    tick(r, clock, 0.05)
    assert r._cursor_now == k.IDC_SIZENESW  # standing: top right, up and out
    assert k.IDC_SIZENESW in _loaded_soon(fake, k.IDC_SIZENESW)
    assert r.host._on_setcursor(r.host.hwnd, 0) == 1  # Windows asks: the host answers with the diagonal
    r._on_event("move", rect[0] - 200, rect[1] + 200)
    tick(r, clock, 0.05)
    _loaded_soon(fake, k.IDC_ARROW, until=lambda: r.host._cursor == 0)
    assert r._cursor_now == 0 and r.host._on_setcursor(r.host.hwnd, 0) is None  # off it: the class arrow
    r.stop()


@pytest.mark.parametrize("hanging,left,want", [(False, False, k.IDC_SIZENESW), (True, False, k.IDC_SIZENWSE), (False, True, k.IDC_SIZENWSE), (True, True, k.IDC_SIZENESW)])
def test_the_diagonal_follows_the_corner(hanging, left, want) -> None:
    from tessellate.core.overlay import sizing

    box = (10, 10, 60, 120)
    hit = sizing.hit_box(box, hanging, 96, left=left)
    assert (k.IDC_SIZENWSE if sizing.pulls_nwse(box, hit, hanging) else k.IDC_SIZENESW) == want


def test_the_ring_is_antialiased_like_the_apps_css_circle() -> None:
    """Its edge has partial alpha (a smooth circle), not only fully clear and fully solid pixels (the old
    aliased draw), and its fill is still the card colour at the centre."""
    from tessellate.core.overlay import sizing

    tile = sizing.ring_tile(48, False)  # 192 dpi: a 12 CSS px circle is 24 px across
    assert any(tile.getchannel("A").histogram()[1:255])  # partial alpha on the edge
    assert tile.getpixel((24, 24))[:3] == sizing.FILL[:3]
    assert tile.getpixel((24, 24 - 11))[3] > 200  # the accent ring at its radius
