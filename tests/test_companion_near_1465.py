"""Its look for controls under it costs nothing while the page holds still (INBOX 1463, 1465).

The owner's lag log: `nameMarkBuddyTick` 198 to 202ms. Its cost was
`nameMarkBuddyObstacles`: a box for every control on the tab and every popup
in the window, read on each idle check (tickcost.js at 4x CPU: 27.7ms on
Notes, 39.1 Library, 26.6 chat, 31.1 dashboard). The checks that only ask
"is anything under me" keep the boxes around its shape (`nameMarkBuddyNear`)
from a sweep kept while the page holds still. The numbers after are in the CHANGELOG line; these pin which
reads each path takes.

Measured on the way (parts2.js, parts3.js): most of the sweep was never the
tab's controls but two selectors over the whole document (the popups and the
floating roots, 6 to 50ms at 4x CPU); they are found by id, class and tag now,
and the tab's boxes are kept while the page holds still.
"""

from __future__ import annotations

import re

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def test_near_keeps_the_boxes_around_its_shape_from_the_kept_sweep() -> None:
    near = _fn("nameMarkBuddyNear")
    assert "nameMarkBuddyShape(x, y, pose, legs)" in near
    assert "nameMarkBuddyObstacles(tab).filter(near)" in near
    # No hit test per point: 60 of them cost as much as the sweep (hitcost.js).
    assert "elementsFromPoint" not in near and "elementFromPoint" not in near


def test_the_tabs_controls_are_measured_once_while_the_page_holds_still() -> None:
    boxes = _fn("nameMarkBuddyControlBoxes")
    assert "nmb.covers?.tab === tab && performance.now() - nmb.covers.at < NMB_COVERS_MAX_MS" in boxes
    assert int(re.search(r"^const NMB_COVERS_MAX_MS = (\d+);$", AV, re.M).group(1)) <= 15000
    # Forgotten on a scroll or resize (the index's reset) and on any change in a tab.
    assert "nmb.covers = null;" in _fn("nameMarkBuddyIndexReset")
    observer = AV[AV.index("const views = new MutationObserver(") :][:900]
    assert "nmb.covers = null;" in observer
    assert "childList: true" in AV[AV.index("views.observe(page,") :][:200]
    # A childList record is not a view shown or hidden.
    assert 'r.type !== "attributes"' in observer
    obstacles = _fn("nameMarkBuddyObstacles")
    assert "nameMarkBuddyControlBoxes(tab)" in obstacles and "querySelectorAll(NAME_MARK_BUDDY_NEVER_COVER)" not in obstacles


def test_no_selector_runs_over_the_whole_document_on_a_look() -> None:
    for name in ("nameMarkBuddyPopups", "nameMarkBuddyFloaters"):
        assert "document.querySelectorAll" not in _fn(name), name
    els = _fn("nameMarkBuddyPopupEls")
    assert "querySelectorAll" not in els
    assert "getElementsByClassName" in els and 'getElementsByTagName("details")' in els and 'getElementsByTagName("dialog")' in els
    # The role menus the app draws, by their classes (roles.js).
    classes = re.search(r"^const NMB_POPUP_CLASSES = \[(.*)\];$", AV, re.M).group(1)
    for name in ("action-menu", "select-menu", "wb-board-menu", "nav-history-menu", "rich-picker-list"):
        assert f'"{name}"' in classes, name


def test_the_checks_that_only_ask_whether_it_covers_use_near() -> None:
    check = _fn("nameMarkBuddyCheck")
    assert check.index("nameMarkBuddyNear(nmb.x, nmb.y, nmb.pose, nmb.legs, tab)") < check.index("nameMarkBuddyObstacles(tab)")
    # The whole sweep only after a hit, to find where to step.
    between = check[check.index("nameMarkBuddyNear(") : check.index("nameMarkBuddyObstacles(tab)")]
    assert ")) return;" in between
    assert "nameMarkBuddyNear(nmb.x, nmb.y, nmb.pose, nmb.legs, tab)" in _fn("nameMarkBuddyBeat")
    assert "nameMarkBuddyObstacles" not in _fn("nameMarkBuddyBeat")
    assert "nameMarkBuddyNear(" in _fn("nameMarkBuddyRefitClear") and "nameMarkBuddyObstacles" not in _fn("nameMarkBuddyRefitClear")
    assert "nameMarkBuddyNear(home.x, home.y, home.pose, home.legs, tab)" in _fn("nameMarkBuddyWander")


def test_the_tick_reads_no_layout_for_the_check_itself() -> None:
    # The check waits a frame and a timer, when the layout is clean, rather
    # than reading inside the tick that just woke.
    tick = _fn("nameMarkBuddyTick")
    assert "queueNameMarkBuddyCheck();" in tick
    assert not re.search(r"^\s*nameMarkBuddyCheck\(\);", tick, re.M)
