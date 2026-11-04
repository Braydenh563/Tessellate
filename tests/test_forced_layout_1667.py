"""Timers and pointer handlers look at a page a frame has drawn (INBOX 1667, the owner's lag logs).

The class: a handler or timer that writes style or the DOM and then reads layout in the same task pays
the page's whole pending style and layout inside it. A browser cannot run in pytest, so these are
static; the measured sweep is `forced.js` (a Playwright probe: CDP `Emulation.setCPUThrottlingRate` 4,
layout-reading calls timed per source line, plus long-animation-frame `forcedStyleAndLayoutDuration`),
and its before and after numbers are in the CHANGELOG line.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _body(src: str, head: str) -> str:
    start = src.index(head)
    return src[start : src.index("\n}\n", start) + 2]


def test_the_act_timer_starts_the_next_act_a_frame_on() -> None:
    src = _src("avatars.js")
    at = src.index("nmb.timer = setTimeout(() => nmb.afterClean(() => {")
    block = src[at : at + 700]
    assert "if (nmb.act !== act) return;" in block, "a replaced act is not ended twice"
    assert "nameMarkBuddyAct(next);" in block


def test_a_travel_step_runs_a_frame_on_unless_the_move_ended() -> None:
    body = _body(_src("companion-travel.js"), "function companionTravelAt(")
    assert "nmb.afterClean(" in body
    assert "nmb.travelTimers === list" in body, "a step of a move that ended or was cut is dropped"


def test_a_mood_hands_over_a_frame_on() -> None:
    mood = _body(_src("atlas.js"), "function setAtlasMood(")
    assert "nmb.afterClean(() => nameMarkBuddyBlend(boxes, apply, 700), 6, apply)" in mood, "a page still being written snaps"
    assert "else apply();" in mood, "the lite set still changes the mood at once"


def test_an_atlas_micro_action_is_played_a_frame_on_and_only_if_still_allowed() -> None:
    body = _body(_src("atlas-micro.js"), "function atlasMicroTick(")
    assert "nmb.afterClean(() => atlasMicroMay(box) && atlasMicroDo(kind, box));" in body


def test_a_tab_press_looks_for_its_scroller_on_a_clean_page() -> None:
    body = _body(_src("phone-shell.js"), "function focusTabPage(")
    assert "nmb.afterClean(focus)" in body
    assert "tabPageScroller(" in body


def test_the_card_grip_looks_once_a_frame_not_once_a_pointerover() -> None:
    src = _src("obj-drag.js")
    assert "overFrame = requestAnimationFrame(look)" in src
    handler = src[src.index('document.addEventListener("pointerover"') :]
    handler = handler[: handler.index("}, true);")]
    assert "movable(" not in handler, "the read of the card happens in the frame callback"
    assert re.search(r"if \(!overFrame\)", handler)


def test_after_clean_can_snap_instead_of_reading_a_page_still_being_written() -> None:
    src = _src("avatars.js")
    assert "afterClean(fn, tries = 6, snap = fn) {" in src
    assert "(dirty ? snap : fn)()" in src


def test_the_card_grip_ignores_a_pointerover_a_scroll_made() -> None:
    src = _src("obj-drag.js")
    assert "performance.now() - scrolledAt < 200" in src
    assert 'window.addEventListener("scroll", () => { scrolledAt' in src


def test_the_atlas_rig_does_not_read_behind_a_dialog() -> None:
    body = _body(_src("atlas-motion.js"), "function atlasRigFrame(")
    assert "nameMarkBuddyBehindCover()" in body[: body.index("const look =")]
