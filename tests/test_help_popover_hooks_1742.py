"""INBOX 1742 (owner screenshots: the reminder date and time pickers opened empty).

Perf audit 1108 P4 moved every help-popover trigger's press onto one capture listener on the document, which stops
the press. A listener a trigger adds for itself never runs after that: the date field never drew its month or its
times, the LAN panel never filled, the tray never took focus, and their "no box, open the sheet" capture listeners
were dead. They now hang off the panel as hooks the shared code calls: `_instead` (open something else this time),
`_beforeOpen` (fill before placing) and `_afterOpen` (fill or focus once placed)."""

from __future__ import annotations

import re

from tests._app_js import app_js_text

JS = app_js_text()


def _file(name: str) -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_the_shared_listener_calls_the_hooks():
    menus = _file("menus.js")
    assert "if (!entry.panel._instead?.()) entry.toggle();" in menus
    open_body = menus[menus.index("  const open = () => {") : menus.index("  entry.toggle = () => {")]
    assert open_body.index("panel._beforeOpen?.();") < open_body.index("placeHelpPopover(panel, trigger);") < open_body.index("panel._afterOpen?.();")


def test_no_wired_trigger_relies_on_its_own_click_listener():
    for name, var in (("date-field.js", "opener"), ("lan-watch.js", "button"), ("obj-tray.js", "button")):
        src = _file(name)
        assert not re.search(rf"\b{var}\.addEventListener\(\s*\"click\"", src), name
    assert "panel._beforeOpen = () => {" in _file("date-field.js")
    assert "panel._instead = () =>" in _file("lan-watch.js") and "panel._afterOpen = () => lanFillPanel(" in _file("lan-watch.js")
    assert "panel._instead = () =>" in _file("obj-tray.js") and "panel._afterOpen = () =>" in _file("obj-tray.js")
