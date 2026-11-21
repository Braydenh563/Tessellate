"""A slow machine changes Atlas's mood without the hand-over (INBOX 1565 note).

At 4x CPU, with the frame budget already holding the lite set (`data-atlas-lite`), the longest
frames left were Atlas's own mood changes: `atlasDrift` 347ms and its back-ease timer 255ms,
222 to 282ms of each a forced restyle. `nameMarkBuddyBlend` reads every part before the change and
again after it, two settles of a page the rig keeps dirty. The hand-over is polish (a loop's end
eased into rest); on a machine that cannot hold 48 fps a snap costs less than the stall, and the
lite set already drops the planets' light and every drift for the same reason.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _mood() -> str:
    start = ATLAS.index("function setAtlasMood(")
    return ATLAS[start : ATLAS.index("\n}\n", start) + 2]


def test_the_lite_set_changes_mood_without_the_hand_over() -> None:
    mood = _mood()
    lite = mood.index('const lite = document.documentElement.hasAttribute("data-atlas-lite");')
    blends = [i for i in range(len(mood)) if mood.startswith("nameMarkBuddyBlend(boxes", i)]
    #: INBOX 1667: the settling timer and the direct call became one hand-over, a frame on (`nmb.afterClean`);
    #: the intent (lite never hands over, the change is still made) is unchanged.
    assert len(blends) == 1, "one hand-over, held back"
    assert lite < min(blends), "asked before either"
    tail = mood[lite : mood.index("if (next === ", lite)]
    assert tail.count("!lite") == 1, "the hand-over waits out the lite set"
    assert tail.rstrip().endswith("else apply();"), "the change is still made"
