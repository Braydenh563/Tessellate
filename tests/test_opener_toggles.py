"""Pressing an opener again closes its menu (INBOX 1626).

The owner: "if I click a button like on the mindmap radial and a popup menu
shows, if I click that button again, I expect the popup menu to close." The
shared openers already toggle (`kebabMenu`, the entry kebab, `enhanceSelect`,
`wireHelpPopover`); the radial's More did not, because its click stops
propagation (the page's outside-click close never sees it) and the page's
outside press has hidden the menu before the click arrives. This reads the
sources and fails on a new `openActionMenu(` call from an opener that has no
close branch, and on the radial losing its press-time read.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

#: Opened by code, not by a press on a button that stays on screen.
PROGRAMMATIC = {"markdown.js": "a menu at a pointer", "selection.js": "the selection menu from the keyboard"}
CLOSE_WORDS = ('classList.contains("hidden")', "closeActionMenus()")


def test_every_opener_has_a_close_branch():
    bad = []
    for path in sorted(JS.glob("*.js")):
        if path.name in PROGRAMMATIC or path.name == "menus.js":
            continue
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\bopenActionMenu\(", src):
            window = src[max(0, m.start() - 600): m.start() + 300]
            if not any(word in window for word in CLOSE_WORDS):
                bad.append(f"{path.name}:{src.count(chr(10), 0, m.start()) + 1}")
    menus = (JS / "menus.js").read_text(encoding="utf-8")
    for m in re.finditer(r"\bopenActionMenu\(menu, opener\)", menus):
        if "closeActionMenus()" not in menus[m.start(): m.start() + 80]:
            bad.append(f"menus.js:{menus.count(chr(10), 0, m.start()) + 1}")
    assert not bad, f"an opener with no way to close its menu on a second press: {bad}"


def test_help_popover_trigger_toggles():
    src = (JS / "menus.js").read_text(encoding="utf-8")
    body = src[src.index("function wireHelpPopover"):]
    body = body[: body.index("window.wireHelpPopover")]
    assert "if (openHelpPopovers.has(entry)) entry.close();" in body


def test_radial_more_closes_on_a_second_press():
    src = frontend_text("whiteboard.js")
    # The press is read in the window's capture phase: the outside-press close
    # has hidden the menu before the click arrives.
    assert "slot._menuWasOpen" in src
    handler = src[src.index('$("wb-radial-more")?.addEventListener("click"'):]
    handler = handler[: handler.index("wbOpenMapNodeMenu(")]
    assert "wasOpen" in handler and "wbCloseContextMenu()" in handler
    assert "slot.focus(" in handler, "focus stays on the button"
