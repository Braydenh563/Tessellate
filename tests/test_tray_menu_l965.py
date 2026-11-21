"""L965: the tray menu is built by `_tray_menu_items`, apart from the tray's
thread and icon, so its order, its separator and its optional console item are
checked here with a stand-in for pystray (the Windows look stays a device check)."""

from __future__ import annotations

import types

from tessellate import __main__ as launcher


class _Item:
    def __init__(self, text, action=None, default=False, checked=None):
        self.text, self.action, self.default, self.checked = text, action, default, checked


class _Menu:
    SEPARATOR = object()


def _pystray():
    module = types.ModuleType("pystray")
    module.MenuItem = _Item
    module.Menu = _Menu
    return module


class _Window:
    def __init__(self):
        self.hidden = 0
        self.scripts: list[str] = []

    def hide(self):
        self.hidden += 1


def _labels(items):
    return ["-" if item is _Menu.SEPARATOR else item.text for item in items]


def test_the_menu_lists_the_features_then_hide_then_restart_and_quit():
    items = launcher._tray_menu_items(_pystray(), _Window(), None, False)
    labels = _labels(items)
    assert labels[0] == "Open Tessellate" and items[0].default
    assert labels[1:9] == [
        "New note", "Ask a question", "Search everything", "Record a meeting",
        "Reminders", "Whiteboard", "Background tasks", "Settings",
    ]  # fmt: skip
    assert labels.index("View Logs") == 9 and labels[10] == "-"
    assert labels[11] == "Hide to tray"
    assert labels[-2:] == ["Restart", "Quit"]
    assert "Hide console window" not in labels


def test_the_companion_item_sits_between_hide_and_restart():
    labels = _labels(launcher._tray_menu_items(_pystray(), _Window(), None, False))
    assert 11 < len(labels) - 2 and len(labels) - 2 - 11 == 2  # Hide to tray, the companion tick


def test_hide_to_tray_hides_the_window():
    window = _Window()
    items = launcher._tray_menu_items(_pystray(), window, None, False)
    next(i for i in items if getattr(i, "text", "") == "Hide to tray").action(None, None)
    assert window.hidden == 1


def test_the_console_item_appears_only_with_a_console_and_reads_its_state():
    shown = launcher._tray_menu_items(_pystray(), _Window(), 1234, True, {1234: "cmd"})
    item = next(i for i in shown if getattr(i, "text", "") == "Hide console window")
    assert item.checked(item) is True
    assert _labels(shown)[-2:] == ["Restart", "Quit"]
    hidden_off = launcher._tray_menu_items(_pystray(), _Window(), 1234, False, {1234: "cmd"})
    assert next(i for i in hidden_off if getattr(i, "text", "") == "Hide console window").checked(None) is False

