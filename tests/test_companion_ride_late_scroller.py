"""B35 (INBOX 904): the companion goes with its panel when the area only began
to scroll after it was perched.

The owner: "Companion doesn't scroll with what it is perched on if the thing
it is perched on is scrollable sometimes on the dashboard."

`nameMarkBuddyGlue` chooses the scroll area once, at the perch. The dashboard
fills in after first paint, so a perch made while it had nothing to scroll
chose no area, never rode, and was then carried by script: measured by
`scratchpad/ui-sweeps/companion1017-dash3.js`, 71px off its panel part-way
through a 240px scroll and 2037px off once settled. The scroll listener now
adopts the area that scrolls under a panel it is not riding yet.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _listener() -> str:
    start = SOURCE.index('document.addEventListener("scroll", (event) => {\n  //: Any scroll, glued or not')
    return SOURCE[start : SOURCE.index("}, { passive: true, capture: true });", start)]


def test_a_scroll_area_met_after_the_perch_is_adopted() -> None:
    body = _listener()
    assert "nameMarkBuddyAdoptScroller(" in body, "a scroll the companion is not riding must be checked for a late area"
    # Before the script follow below it, which would carry it by hand.
    assert body.index("nameMarkBuddyAdoptScroller(") < body.index("nameMarkBuddyFollow();")


def test_adoption_takes_only_the_nearest_area_the_panel_really_scrolls_with() -> None:
    start = SOURCE.index("function nameMarkBuddyAdoptScroller(")
    body = SOURCE[start : SOURCE.index("\n}\n", start)]
    assert "nameMarkBuddyScroller(g.el) !== target" in body
    assert "nameMarkBuddyScrollsWith(g.el, target)" in body
    assert "nameMarkBuddyRide(target" in body
