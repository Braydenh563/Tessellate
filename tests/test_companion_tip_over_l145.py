"""L145 in the app: a thrown companion drops what it holds. Grabbed in a prop act, the prop lies tipped over at its feet for
`NMB_THROW.tip` once it has landed (`companionThrowTip`, `nmb-tip-<act>` in atlas-lazy.css), as the desk's does (`props.TIP_PROPS`)."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core.overlay import props
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
TH = unwrapped((ROOT / "frontend" / "js" / "companion-throw.js").read_text(encoding="utf-8"))
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
TIP_ACTS = re.findall(r'"(\w+)"', re.search(r"const NMB_TIP_ACTS = \[([^\]]*)\]", AV).group(1))
#: The app's act for the desk's prop (the ones the two have in common).
DESK = {"tea": "cup", "fish": "rod", "journal": "journal", "plant": "plant", "dinner": "bowl", "bubbles": "wand", "weights": "dumbbell"}


def test_every_act_that_drops_its_prop_is_a_desk_act_with_a_slot_that_lies_on_its_side() -> None:
    assert TIP_ACTS and len(set(TIP_ACTS)) == len(TIP_ACTS)
    for act in TIP_ACTS:
        assert re.search(rf"^\s*{act}: \{{[^}}]*desk: true", AV, re.M), act
        rule = re.search(rf"#nm-buddy\.nmb-tip-{act} [^{{]*", LAZY)
        assert rule, f"no tipped-over rule for {act}"
    body = LAZY[LAZY.index("L145: a thrown companion drops what it holds") :]
    assert "rotate: 80deg" in body and "opacity: 1" in body and "translate: 0 24px" in body


def test_the_app_and_the_desk_drop_the_same_props() -> None:
    for act, prop in DESK.items():
        assert act in TIP_ACTS, act
        assert prop in props.TIP_PROPS, prop


def test_it_is_armed_when_grabbed_and_laid_down_when_it_lands_and_not_without_motion() -> None:
    halt = AV[AV.index("function nameMarkBuddyHalt(buddy)") :][:300]
    assert "NMB_TIP_ACTS.includes(nmb.act)" in halt and "nmb.tipAct = nmb.act" in halt
    land = TH[TH.index("const land = () => {") :][:1300]
    tip = land
    assert "nmb.tipAct" in land and "15000" in land and "nameMarkBuddyStill()" in land, "a pick-up with no throw, or no motion, leaves nothing lying"
    assert "setTimeout(" in tip and "classList.remove(`nmb-tip-${tipAct}`)" in tip and "NMB_THROW.tip" in tip
