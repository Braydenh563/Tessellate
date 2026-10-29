"""A menu's trigger toggles (INBOX 681) and the Settings sidebar follows (INBOX 680).

The suite cannot see a browser, so these pin the two shapes the fixes took;
the behaviour itself is measured by `scratchpad/ui-sweeps/toggles681.js` (every
trigger on every tab pressed twice, then Enter twice) and
`scratchpad/ui-sweeps/settingsfollow680.js`.

**Why a press on the opener must not close the menu.** The outside-press closer
runs on `pointerdown`, before the opener's own `click`. A custom select's opener
sits in `.select-shell`, outside `.menu-wrap`, so the press closed the list and
the click that followed opened it again: the second press never shut it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = ROOT / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_outside_press_closer_leaves_the_opener_alone():
    src = _read("settings-wiring.js")
    block = re.search(r'document\.addEventListener\("pointerdown", \(e\) => \{(.*?)\}, true\);', src, re.S)
    assert block, "the outside-press closer moved: update this test with it"
    body = block.group(1)
    assert "[aria-haspopup][aria-expanded='true']" in body


def test_chip_menu_is_its_chips_opener_and_toggles():
    src = _read("chip-menus.js")
    # The chip is the menu's opener for the closer (`closeActionMenus` resets
    # its aria-expanded), and the closer's press exception reads that state.
    assert "menu._escapedOpener = chipEl" in src
    assert 'chipEl.setAttribute("aria-expanded", "true")' in src
    assert 'x === undefined && chipEl.getAttribute("aria-expanded") === "true"' in src


def test_settings_sidebar_follow_never_moves_focus_and_respects_motion():
    src = _read("settings-find.js")
    follow = re.search(r"function settingsNavFollow\(link\) \{(.*?)\n\}\n", src, re.S)
    assert follow, "settingsNavFollow is gone"
    body = follow.group(1)
    assert ".focus(" not in body and "scrollIntoView" not in body
    assert "uiMotion" in body and "prefers-reduced-motion" in body
    assert ":hover" in body, "the sidebar must be left alone while the pointer is over it"
    assert "settingsNavFollow(link)" in src.split("function settingsIndexMark")[1]


def test_settings_nav_headings_open_their_first_page_and_the_index_is_one_short_block():
    """INBOX 697 and 698, the shapes: a heading is in the nav's click loop, and
    the in-page index is collapsed to the current link unless the person asked
    for all of it (remembered under one key)."""
    settings = _read("settings.js")
    assert '"#settings-nav button, #settings-nav .nav-group-label"' in settings
    find = _read("settings-find.js")
    assert "settings-nav-sections" in find and "Show all ${nounCount(heads.length, \"section\")}" in find
    css = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert ".settings-nav-groups:not(.is-open) .settings-nav-group:not([aria-current=\"location\"])" in css
    label = re.search(r"#settings-nav \.nav-group-label \{(.*?)\}", css, re.S)
    assert label and "cursor: default" in label.group(1) and "var(--text-xs)" in label.group(1)
