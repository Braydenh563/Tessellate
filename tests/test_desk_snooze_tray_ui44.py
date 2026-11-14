"""Source text: Hide for 10 minutes hides the figure and the card, and nothing
on screen carried a countdown. While it is hidden the tray shows when it comes
back and brings it back now (L-ui-modernisation-44)."""

# ruff: noqa: F811  (pytest fixtures are used by name)
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PIL")

from tessellate.core import desk_companion as dc  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402, F401
from tests.test_desk_overlay_wiring import over  # noqa: E402, F401


class Item:
    def __init__(self, text, action, visible=True, **_):
        self.text, self.action, self.visible = text, action, visible


def test_the_tray_shows_the_snooze_and_ends_it(over, monkeypatch) -> None:
    """Source text: the tray shows when it comes back and brings it back now."""
    clock = {"t": 1000.0}
    over._now = lambda: clock["t"]
    monkeypatch.setattr(dc, "_active", over)
    monkeypatch.setattr(dc, "_clock_text", lambda seconds_from_now: f"in {round(seconds_from_now)}s")
    item = dc.tray_snooze_item(SimpleNamespace(MenuItem=Item))
    over.set_main_hidden(True)
    assert item.visible(item) is False
    over.snooze()
    over._snooze_timer.cancel()
    assert not over.shown and item.visible(item) is True
    clock["t"] += 60
    assert item.text(item) == "Companion back in 540s: show it now"
    item.action(None, item)
    over.sync()
    assert over.shown and item.visible(item) is False


def test_the_tray_is_redrawn_when_a_snooze_starts_and_ends(over, monkeypatch) -> None:
    """Source text: a backend without dynamic menus redraws the snooze line only when told."""
    drawn = []
    monkeypatch.setattr(dc, "_tray_refresh", lambda: drawn.append(1))
    over.set_main_hidden(True)
    over.snooze()
    over._snooze_timer.cancel()
    over.end_snooze()
    assert len(drawn) == 2


def test_the_launcher_lists_the_snooze_line_and_wires_the_redraw() -> None:
    """Source text: while it is hidden the tray shows when it comes back."""
    from tests._app_js import FRONTEND_DIR

    main = (FRONTEND_DIR.parent / "src/tessellate/__main__.py").read_text()
    assert "desk_companion.tray_snooze_item(pystray)" in main
    #: Through the marshal (review 5899359161): the win32 rebuild runs on the tray thread.
    assert "desk_companion.set_tray_refresh(desk_companion.tray_marshal(icon))" in main
    assert "on_change=desk_companion.tray_marshal(tray_icon)" in main


class _WinIcon:
    """pystray's win32 Icon as far as the marshal reads it."""

    def __init__(self):
        self._message_handlers = {}
        self._hwnd = 7
        self.rebuilt = 0

    def update_menu(self):
        self.rebuilt += 1


def test_a_win32_tray_rebuilds_its_menu_on_its_own_loop():
    # Review 5899359161 (4): pystray's win32 `update_menu` destroys and rebuilds the menu handle on the
    # calling thread, which raced the tray thread showing it; the refresh now posts to the tray's window.
    icon, posted = _WinIcon(), []
    refresh = dc.tray_marshal(icon, post=lambda *a: posted.append(a))
    refresh()
    assert icon.rebuilt == 0 and posted == [(7, dc.WM_TRAY_MENU, 0, 0)]
    icon._message_handlers[dc.WM_TRAY_MENU](0, 0)
    assert icon.rebuilt == 1


def test_a_tray_not_yet_running_is_not_posted_to():
    icon, posted = _WinIcon(), []
    icon._hwnd = None
    dc.tray_marshal(icon, post=lambda *a: posted.append(a))()
    assert posted == [] and icon.rebuilt == 0


def test_a_backend_that_marshals_itself_is_called_directly():
    # GTK and AppIndicator wrap `_update_menu` in their own main-loop call; Xorg has no menu.
    class Gtk:
        def update_menu(self):
            pass

    icon = Gtk()
    assert dc.tray_marshal(icon) == icon.update_menu
    assert dc.tray_marshal(None) is None
