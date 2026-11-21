"""Her raised arms turn about her shoulders and the carry act has its note (INBOX 1589 leftovers).

- The raised-arm drawings (`.nmb-hold`, shown hanging, carried, in a cheer or a stretch) turned about
  his shoulders, `24.6px 41px` and `37.4px 41px` (characters-lazy.css; 25.6 and 36.4 since INBOX 1607 b). Her arms
  are rooted 1.8 units further in, `armPivots` (`ATLAS_LOOKS.feminine`), and the hold is drawn from that root: turned about
  his, its shoulder swung out of the torso as her arms once did (INBOX 612). It takes the same pivot
  as the arm, inline, wherever the look names one.
- The carry act ("carrying a note it just filed") showed nothing in Atlas's hand, where the classic
  companion has its `nmp-note`. Atlas draws one in the hand slot beside the bell and the lantern, from
  the prop classes that exist (`atl-prop-page`, `atl-prop-page-edge`, `atl-node-dot`), and the sheet
  that shows the classic's note shows it.
"""

from __future__ import annotations

import re

from pathlib import Path
from tests._css_paths import sheets

ROOT = Path(__file__).resolve().parents[1]
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
CSS = sheets("05-sidebars-themes.css", "characters-lazy.css")


def _fn(name: str) -> str:
    start = ATLAS.index(f"function {name}(")
    return ATLAS[start : ATLAS.index("\n}\n", start) + 2]


def test_the_hold_arms_take_the_looks_shoulder_pivots_like_the_arms() -> None:
    body = _fn("atlasBody")
    holds = body[body.index("for (const [side, d] of ATLAS_LIMBS.holds) {") :]
    holds = holds[: holds.index("\n    }\n")]
    line = "if (spec.armPivots) %s.style.transformOrigin = spec.armPivots[side].map((v) => `${v}px`).join(\" \");"
    assert line % "hold" in holds, "the hold names its look's pivot"
    assert line % "arm" in body[body.index("`nmb-arm nmb-arm-${side}`") :][:900], "as the arm does"


def test_the_css_origin_stays_the_masculine_default_for_a_look_without_pivots() -> None:
    # Intent moved (INBOX 1607 b): his shoulders narrowed and his arms' roots came in by 1 with them,
    # so his default origin is 25.6 and 36.4; it is still his, the look without pivots.
    assert "#nm-buddy .atl-figure .nmb-hold-l { transform-origin: 25.6px 41px; }" in CSS
    assert "#nm-buddy .atl-figure .nmb-hold-r { transform-origin: 36.4px 41px; }" in CSS


def test_atlas_holds_a_note_in_the_hand_slot_for_the_carry_act() -> None:
    props = _fn("atlasHandProps")
    assert 'atlasGroup(upright, "nmp nmp-note")' in props
    note = props[props.index('"nmp nmp-note"') :]
    note = note[: note.index("const bell")]
    classes = set(re.findall(r'class: "([^"]+)"', note))
    assert classes == {"atl-prop-page", "atl-prop-page-edge", "atl-node-dot"}, "drawn from the existing prop classes"
    assert "#nm-buddy.nmb-act-carry .nmp-note," in CSS, "the sheet that shows the classic's note shows it"
