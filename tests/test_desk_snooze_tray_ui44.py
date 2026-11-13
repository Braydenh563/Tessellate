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
    assert "desk_companion.set_tray_refresh(icon.update_menu)" in main
