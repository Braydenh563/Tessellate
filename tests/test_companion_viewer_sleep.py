"""The companion asleep in its large view, and its focus (the owner, 2026-10-11).

"the zzz isnt animated ... on this panel"; a blue rounded rectangle round the
sleeping companion; "a bit glitchy" under load. Measured in a browser by
`scratchpad/ui-sweeps/viewersleep.js` (the Zs' running animations and
opacity over 7s in the view, the ring after a click and after Tab, CPU=6 for
CDP throttling). These pin the wiring those numbers rest on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = "\n".join((ROOT / "frontend" / "js" / n).read_text(encoding="utf-8") for n in ("avatars.js", "companion-menu.js"))
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def test_falling_asleep_ends_the_act_under_way() -> None:
    # A wave held on under the Zs was the stuck pose (viewersleep.js:
    # "nmb-act-wave nmb-sleep" for 7s).
    tick = _fn("nameMarkBuddyTick")
    branch = tick[tick.index("if (idle > NMB_SLEEP_MS && !awake)") :]
    end = branch.index('nameMarkBuddyAct("")')
    assert end < branch.index('buddy.classList.add("nmb-sleep")')
    assert "!NMB_RESTING_ACTS.has(nmb.act)" in branch[:end]


def test_coming_back_to_the_page_ends_an_act_whose_timer_hiding_cleared() -> None:
    listener = AV[AV.index("//: Back after a long absence, it is found asleep") - 400 :]
    listener = listener[: listener.index("nameMarkBuddySchedule();")]
    assert 'if (nmb.act && !NMB_RESTING_ACTS.has(nmb.act)) nameMarkBuddyAct("");' in listener


def test_arriving_in_the_view_under_a_still_pointer_is_not_a_hover() -> None:
    visit = _fn("nameMarkBuddyVisit")
    assert "at: Date.now()" in visit
    enter = AV[AV.index('face.addEventListener("pointerenter"') :]
    enter = enter[: enter.index("nameMarkBuddyHover(0);")]
    assert "nmb.visit && Date.now() - nmb.visit.at < NMB_VISIT_SETTLE_MS" in enter


def test_its_focus_is_a_glow_from_the_keyboard_only() -> None:
    assert re.search(r"#nm-buddy \.nm-buddy-face:is\(:focus, :focus-visible\) \{ outline: none; \}", CSS)
    glow = CSS[CSS.index("#nm-buddy .nm-buddy-face::before {") :]
    glow = glow[: glow.index("}")]
    assert "border-radius: 50%" in glow and "radial-gradient" in glow and "opacity: 0" in glow
    assert "#nm-buddy .nm-buddy-face:focus-visible::before { opacity: 1; }" in CSS
    # No filter on the moving figure for it.
    assert "drop-shadow" not in glow


def test_the_reduce_hint_stops_atlas_figure_loops_and_keeps_acts() -> None:
    # Ledger 669, INBOX 772: under the system hint the figure's float, bob and
    # glide stop (they were slowed to 6s); an act, one gesture that ends, plays.
    assert "#nm-buddy:has(.atl-figure) .nm-buddy-char,\n" not in CSS, "the 6s slow-down is gone"
    block = CSS[CSS.index("ledger 669") :]
    block = block[: block.index("\n}\n")]
    assert '#nm-buddy:has(.atl-figure):is(.nmb-walking, [data-pose="float"]) .nm-buddy-char { animation: none !important; }' in block
    assert "#nm-buddy:is(.nmb-walking, .nm-buddy-dragging) .nm-live .nm-atlas.atl-layer-lower," in block
    assert "[class*=" not in block, "a class attribute selector up the tree restyles the subtree on every class change"
    assert "nmb-act" not in block.split("*/")[-1], "an act, one gesture, still plays"


def test_the_idle_pool_never_reaches_for_one_of_the_last_five_acts() -> None:
    # Brief 34 step 5, ledger 678/679 ("more varied"): the act just played and
    # the four before it sit out while anything else suits the moment.
    act = _fn("nameMarkBuddyAct")
    assert "nmb.recentActs = [act, ...(nmb.recentActs || []).filter((a) => a !== act)].slice(0, NMB_RECENT_ACTS);" in act
    assert act.index("if (!act) {") < act.index("nmb.recentActs ="), "clearing an act is not an act"
    decide = _fn("nameMarkBuddyDecide")
    assert "const fresh = pool.filter(([act]) => !recent.includes(act));" in decide
    assert "if (fresh.length && fresh.length < pool.length)" in decide, "a pool of only recent acts still picks"
    assert AV.index("const NMB_RECENT_ACTS = 5;") < AV.index("function nameMarkBuddyAct(")
