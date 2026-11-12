"""Timers and pointer handlers look at a page a frame has drawn (INBOX 1667, the owner's lag logs).

The class: a handler or timer that writes style or the DOM and then reads layout in the same task pays
the page's whole pending style and layout inside it. A browser cannot run in pytest, so these are
static; the measured sweep is the 1674 probe `cat_probe.js` (MODE=perf, kept in the agent's scratch dir:
CDP `Emulation.setCPUThrottlingRate` 4, long-animation-frame `forcedStyleAndLayoutDuration` per script
line), and its before and after numbers are in the CHANGELOG line.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name: str) -> str:
    return unwrapped((JS / name).read_text(encoding="utf-8"))


def _body(src: str, head: str) -> str:
    start = src.index(head)
    return src[start : src.index("\n}\n", start) + 2]


def test_the_act_timer_starts_the_next_act_a_frame_on() -> None:
    src = _src("avatars.js")
    at = src.index("const own = (nmb.timer = setTimeout(() => nmb.afterClean(() => {")
    block = src[at : at + 700]
    assert "if (nmb.act !== act || nmb.timer !== own) return;" in block, "a replaced or restarted act is not ended twice"
    assert "const own = (nmb.timer = setTimeout(" in src
    assert "nameMarkBuddyAct(next);" in block


def test_a_travel_step_runs_a_frame_on_unless_the_move_ended() -> None:
    body = _body(_src("companion-travel.js"), "function companionTravelAt(")
    assert "nmb.afterClean(" in body
    assert "nmb.travelTimers === list" in body, "a step of a move that ended or was cut is dropped"


def test_a_mood_hands_over_a_frame_on() -> None:
    mood = _body(_src("atlas.js"), "function setAtlasMood(")
    assert "nmb.afterClean(() => nameMarkBuddyBlend(boxes, latest, 700), 14, latest, 160)" in mood, "a page still being written snaps"
    assert "else apply();" in mood, "the lite set and a hidden tab still change the mood at once"
    assert "!document.hidden" in mood, "a hidden tab has no frames to wait for"


def test_only_the_newest_mood_call_applies() -> None:
    mood = _body(_src("atlas.js"), "function setAtlasMood(")
    assert "const seq = (setAtlasMood.seq = (setAtlasMood.seq || 0) + 1);" in mood
    assert mood.count("seq === setAtlasMood.seq") == 2, "the timer and the closure both drop a superseded call"


def test_an_atlas_micro_action_is_played_a_frame_on_and_only_if_still_allowed() -> None:
    body = _body(_src("atlas-micro.js"), "function atlasMicroTick(")
    assert "nmb.afterClean(() => atlasMicroMay(box) && atlasMicroDo(kind, box));" in body


def test_a_tab_press_looks_for_its_scroller_on_a_clean_page() -> None:
    body = _body(_src("phone-shell.js"), "function focusTabPage(")
    assert "nmb.afterClean(focus)" in body
    assert "tabPageScroller(" in body


def test_the_card_grip_looks_once_a_frame_not_once_a_pointerover() -> None:
    src = _src("obj-drag.js")
    # the file's one frame helper (afterFrames), not a second raf in obj-drag.js (the wake-source ratchet)
    assert "afterFrames(() => setTimeout(look), 1)" in src
    handler = src[src.index('document.addEventListener("pointerover"') :]
    handler = handler[: handler.index("}, true);")]
    assert "movable(" not in handler, "the read of the card happens in the frame callback"
    assert re.search(r"if \(!overFrame\)", handler)


def test_after_clean_can_snap_instead_of_reading_a_page_still_being_written() -> None:
    src = _src("avatars.js")
    assert "afterClean(fn, tries = 6, snap = fn, calm = 0) {" in src
    assert "afterCalm(fn, rounds = 4) {" in src, "and afterCalm lets a look go rather than read a page that stays dirty (INBOX 1766)"
    assert "(dirty ? snap : fn)()" in src


def test_the_card_grip_ignores_a_pointerover_a_scroll_made() -> None:
    src = _src("obj-drag.js")
    assert "performance.now() - scrolledAt < 200" in src
    assert "scrolledAt = performance.now();" in src
    assert "document.elementFromPoint(rest.x, rest.y)" in src, "a resting pointer is looked at once the scroll is still"


def test_the_atlas_rig_does_not_read_behind_a_dialog() -> None:
    # (Since INBOX 1766 the look is its own task, `atlasRigLook`; the frame reads nothing.)
    body = _body(_src("atlas-motion.js"), "atlasRigWake.look = function atlasRigLook(")
    assert "nameMarkBuddyBehindCover()" in body[: body.index("const reads =")]


def test_the_first_run_toast_poll_reads_no_layout() -> None:
    """The welcome waits for toasts to clear every 250 ms; a `getClientRects()` there laid the page out each time."""
    body = _body(_src("onboarding.js"), "function firstRunToastsGone")
    code = "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))
    assert "getClientRects" not in code and "getBoundingClientRect" not in code
    for hidden in (".is-leaving", ".is-folded", ".is-behind", ".toast-more"):
        assert hidden in body.split("querySelector(")[1].split(")")[0], hidden


def test_the_perch_check_waits_for_an_idle_frame_rather_than_reading_a_page_still_being_written() -> None:
    """1667 (44 notes, notes tab): `afterClean` ran the sweep after six dirty tries, laying the page out inside the timer."""
    body = _body(_src("avatars.js"), "function queueNameMarkBuddyCheck(")
    assert "nmb.afterClean(look, 6, wait);" in body, "the dirty branch is not the sweep itself"
    assert "requestIdleCallback(again" in body and "later - 1" in body, "it asks again on an idle frame, a bounded number of times"
    assert "if (later < 1) return look();" in body, "a page that never goes quiet is still looked at"


def test_a_release_takes_the_ledges_before_its_writes_and_the_placement_keeps_them() -> None:
    """1698-lag (`avatars.js release 3222ms, forced layout 2965ms`): the ledges' rects were read after the release's writes."""
    src = _src("avatars.js")
    release = src[src.index("const release = (event) => {") :]
    release = release[: release.index('face.addEventListener("pointerup", release);')]
    assert release.index("if (landed) nmb.place.read(landed);") < release.index('buddy.style.translate = "";', release.index("const landed")), "read before the first write"
    read = _body(src, "  read(spot) {").split("\n  },")[0]
    assert "if (!this.boxes) {" in read and "!this.boxes.has(bar)" in read, "a second read in the stack adds only what is missing"


def test_a_hover_over_the_figure_is_judged_once_a_frame_not_read_on_every_move() -> None:
    src = _src("avatars.js")
    move = src[src.index("const judgeRub = () => {") :]
    move = move[: move.index('face.addEventListener("pointerleave"')]
    assert "afterFrames(judgeRub, 1)" in move
    handler = move[move.index('face.addEventListener("pointermove"') :]
    assert "getBoundingClientRect" not in handler, "the pointermove handler itself reads no layout"
