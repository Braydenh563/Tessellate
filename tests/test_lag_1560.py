"""INBOX 1560 (the owner's Windows lag logs, 2026-11-03): each test names the cost it keeps out.

Measured at 4x CPU on a notebook with a long list in every tab page (about 40,000 elements,
Atlas on): the look for popups walked the whole document and a hidden page keeps its list drawn.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def test_the_popup_walk_skips_the_pages_that_are_not_shown():
    # 38.4ms to 0.6ms a walk at 4x CPU (39,750 elements, five hidden pages with a long list each);
    # a popup in a hidden page has no box, so the set of shown popups is the same (0 missed).
    roots = AV[AV.index("  liveRoots() {") :][:420]
    assert 'child.classList.contains("hidden")' in roots and 'child.id !== "app-main"' in roots
    assert 'page.classList.contains("hidden")' in roots
    els = _fn("nameMarkBuddyPopupEls")
    assert "nmb.liveRoots()" in els
    assert "document.getElementsByClassName" not in els and "document.getElementsByTagName" not in els
    # A root can itself be the popup (a dialog, a help popover appended to the body).
    assert 'root.localName === "dialog" && root.open' in els and "root.classList.contains(name)" in els


def test_the_floating_roots_are_found_the_same_way():
    floaters = _fn("nameMarkBuddyFloaters")
    assert "nmb.liveRoots()" in floaters and "document.getElementsByClassName" not in floaters
    for name in ("pointer-menu-host", "dock-fab", "chat-jump-latest", "modal-overlay"):
        assert f'"{name}"' in floaters, name


def test_the_beat_looks_after_a_frame_has_drawn():
    # The first box read of a look settled the layout the frame was about to do anyway (the log:
    # 156ms with 98 forced, and 1838 with 1727 on the Library). One frame and a timer on, as the check.
    beat = _fn("nameMarkBuddyBeat")
    assert beat.index("document.hidden") < beat.index("afterFrames(() => setTimeout(")
    assert beat.index("afterFrames(() => setTimeout(") < beat.index("nameMarkBuddyTab()")
    assert "if (!nmb.beatDue) {" in beat and "nmb.beatDue = true;" in beat and "nmb.beatDue = false;" in beat
    assert "nmb.beatFrame" in beat
