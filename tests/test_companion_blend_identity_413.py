"""A transform in a transition's delay is not a move (L-world-class-413, companionacts.js).

Lying down has a 240ms transition delay, during which the browser reads the figure's
transform as the identity matrix where it read "none" before. The hand-over between acts
(`nameMarkBuddyBlend`) took that string difference for a move and eased the figure to the
end pose over 300ms, after which it snapped back to the start and began again: 20px in one
frame going into a lie (companionacts.js, now 1.7px; the beanbag 14.1px, now 0.7px).
"""

import re
from pathlib import Path

AVATARS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _blend():
    m = re.search(r"function nameMarkBuddyBlend\(.*?\n  function nameMarkBuddyEase", AVATARS, re.S)
    assert m, "nameMarkBuddyBlend moved"
    return m.group(0)


def test_identity_matrix_and_none_are_the_same_pose():
    src = _blend()
    assert 'x === "none" || x === "matrix(1, 0, 0, 1, 0, 0)"' in src


def test_both_move_filters_use_it():
    src = _blend()
    assert "!same(style[key], from[key])" in src
    assert src.count("!same(style[key], from[key])") == 2
    assert "style[key] !== from[key]" not in src
