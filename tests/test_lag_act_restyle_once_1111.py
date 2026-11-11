"""lag 1111: an act's hand-over settles the page once, not twice.

`nameMarkBuddyBlend` reads where the parts are before its change and again after it. The first read settles
whatever is dirty, and `nameMarkBuddyAct` used to write the ease class (`nmb-easing`) and `data-variant` ahead of
the hand-over, so that read paid a restyle of those two writes (11 to 19ms at 4x CPU, Documents with 30k nodes)
and the change's restyle then covered the same elements again. Written inside `leave` and `into`, which the
hand-over runs as its change, the page settles once, after the parts have been read where they are.

Measured the same session (4x CPU, 30k nodes, 3 runs of 6 acts, start and end of each, median/max):
the hand-over's first `getAnimations` 16.8/28.6ms to 0.3/3.1ms; the whole hand-over 43.4,40.8/184,147ms to
30.0,27.0/107,106ms; the largest one-frame move of any part across the call 4.8px before and after.
What is left is the act's own restyle (the class change on `#nm-buddy`, 20ms median and up to 95ms for a cheer or
a read, whose custom properties restyle the whole figure): it is the same for `document.getAnimations()`,
`getAnimations({subtree})`, one element's `getAnimations()` and a `getComputedStyle`, containment on the companion
does not shrink it, and with no hand-over at all it lands in the next frame instead (62.9 against 65.4ms of
restyles over 100 elements). It cannot be cut from the hand-over; see atlasmotion-1111.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _block(src: str, head: str) -> str:
    start = src.index(head)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(head)


def _code(body: str) -> str:
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))


def test_the_ease_class_is_written_by_the_hand_over_not_ahead_of_it() -> None:
    act = _code(_block(AV, "function nameMarkBuddyAct("))
    leave = _block(act, "const leave = () => {")
    assert act.count("nameMarkBuddyEase(") == 1, "one call, inside leave"
    assert leave.index("if (easeOut) nameMarkBuddyEase(buddy, 1800);") < leave.index("classList.remove(`nmb-act-${was}`)")
    assert "const easeOut = !!was && was !== act && !NMB_FACELESS_ACTS.includes(was);" in act


def test_the_variant_is_written_by_the_hand_over_not_ahead_of_it() -> None:
    act = _code(_block(AV, "function nameMarkBuddyAct("))
    into = _block(act, "const into = () => {")
    assert len(re.findall(r"dataset\.variant\b", act)) == 2, "set and delete, both in `into`"
    assert len(re.findall(r"dataset\.variant\b", into)) == 2
    assert "if (variant) buddy.dataset.variant = variant;" in into and "delete buddy.dataset.variant;" in into
    # The pick (and its memory, so the next pick differs) stays where it was; only the write moved.
    assert "variant = String(v);" in act and "nmb.variant = { ...(nmb.variant || {}), [act]: v };" in act


def test_no_hand_over_in_the_act_follows_a_style_write_of_the_act() -> None:
    # Everything the act writes to #nm-buddy's classes or attributes before its first hand-over would be settled by
    # the hand-over's first read; `nmb-duck` and `data-turn` are acts' own and removed only when set.
    act = _code(_block(AV, "function nameMarkBuddyAct("))
    first = act.index("nameMarkBuddyBlend(")
    before = act[:first]
    assert "dataset.variant" not in before.replace("nmb.variant", "") and "nameMarkBuddyEase(buddy" not in before.replace("if (easeOut) nameMarkBuddyEase(buddy, 1800);", "")
