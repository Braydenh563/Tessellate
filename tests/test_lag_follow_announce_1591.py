"""A page's transition that cannot move a panel does not keep the follow loop alive (INBOX 1591, the lag log).

The Focus timer widget redraws its ring every second (`stroke-dashoffset`, a `transitionrun` each
time). Every `transitionrun` stamped `nmbFollow.animAt` and kept the follow loop up, so with Atlas
perched on that card `nameMarkBuddyPanelMoving` asked `getAnimations()` for ever: 157 forced style
settles in 30s at 4x CPU, 5.1 s of them, 169ms at most (the owner's dashboard: frames of 1.9 and 2.1 s).
A transition names its property (`event.propertyName`); one that places no box (`NMB_PLACES`) announces
nothing, as a scroll of an unrelated panel does not.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AVATARS = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _listener() -> str:
    start = AVATARS.index('for (const type of ["pointerdown", "pointerup", "keydown", "transitionrun"')
    return AVATARS[start : AVATARS.index("\n}\n", start) + 3]


def test_a_transition_that_places_no_box_announces_nothing() -> None:
    body = _listener()
    gate = body.index("NMB_PLACES.test(event.propertyName)")
    assert gate < body.index("nmbFollow.animAt = performance.now()"), "asked before the stamp"
    assert gate < body.index("nameMarkBuddyKeepUp("), "and before the loop is kept up"
    assert "return;" in body[gate : body.index("nmbFollow.animAt")], "the handler leaves"


def test_the_gate_is_for_transitions_only() -> None:
    body = _listener()
    gate = body.index("NMB_PLACES.test(event.propertyName)")
    before = body[body.rindex("\n", 0, gate) : gate]
    assert 'type.startsWith("transition")' in before, "an animation names no property: it is still announced"
