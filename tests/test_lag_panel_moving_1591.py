"""Asking whether the panel is moving settles style once a look, not once a read (INBOX 1591).

`nameMarkBuddyPanelMoving` calls `document.getAnimations()`, which settles the page's
whole style when anything is dirty. Measured at 4x CPU with Atlas perched on a card that
slides: 52 calls in 4.7 s, 32 of them forced style recalcs, the largest single source of
them (286ms of main thread, 24 forced recalcs a second in all). Two causes:

- `nameMarkBuddyCatchUp` asks it again on every frame of a move, after the frame's own
  writes, though the follow loop asked 120ms ago;
- the follow loop asked it after `nameMarkBuddyFollow` had written the buddy's place,
  a read-after-write that settled style a second time in the frame.

The answer is kept for the loop's own 120ms unless something has been set going since
(`nmbFollow.animAt`), and the frame asks before it writes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _const(name: str) -> str:
    return re.search(rf"^const {name} = .*;$", AV, re.M).group(0)


def _run(steps: str):
    script = "\n".join(
        [
            "let NOW = 1000, asked = 0;",
            "const performance = { now: () => NOW };",
            "const page = { isConnected: true, contains: (n) => n === page };",
            "const other = { isConnected: true, contains: (n) => n === other };",
            "const slide = { playState: 'running', transitionProperty: 'transform', effect: { target: page, getComputedTiming: () => ({ endTime: 400 }) } };",
            "let anims = [slide];",
            "const document = { getAnimations: () => { asked++; return anims; }, getElementById: () => null };",
            "const nmbFollow = { animAt: 0, pm: { el: null, at: -1e9, val: false } };",
            _const("NMB_PLACES"),
            _const("NMB_LAYOUT"),
            _fn("nameMarkBuddyAnimProps"),
            _fn("nameMarkBuddyPanelMoving"),
            "const out = {};",
            steps,
            "console.log(JSON.stringify(out));",
        ]
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_second_ask_inside_the_loops_120ms_is_answered_without_a_read() -> None:
    got = _run("out.a = nameMarkBuddyPanelMoving(page); NOW += 16; out.b = nameMarkBuddyPanelMoving(page); NOW += 16; out.c = nameMarkBuddyPanelMoving(page); out.asked = asked;")
    assert (got["a"], got["b"], got["c"]) == (True, True, True)
    assert got["asked"] == 1, "one getAnimations for the three asks of a 120ms window"


@needs_node
def test_it_asks_again_after_120ms_for_another_panel_and_after_something_starts() -> None:
    got = _run(
        "nameMarkBuddyPanelMoving(page); NOW += 130; nameMarkBuddyPanelMoving(page); out.late = asked;"
        "nameMarkBuddyPanelMoving(other); out.other = asked;"
        "NOW += 10; nmbFollow.animAt = NOW; NOW += 1; anims = []; out.fresh = nameMarkBuddyPanelMoving(other); out.started = asked;"
    )
    assert got["late"] == 2, "a window is 120ms"
    assert got["other"] == 3, "the answer is for the panel asked about"
    assert got["started"] == 4 and got["fresh"] is False, "an animation set going since the last look is looked for"


@needs_node
def test_the_answer_is_still_whether_a_place_changing_animation_runs() -> None:
    got = _run("anims = [{ playState: 'running', transitionProperty: 'opacity', effect: { target: page } }]; out.fade = nameMarkBuddyPanelMoving(page); NOW += 200; anims = [slide]; out.slide = nameMarkBuddyPanelMoving(page);")
    assert got == {"fade": False, "slide": True}


def test_the_follow_frame_asks_before_it_writes() -> None:
    frame = _fn("nameMarkBuddyFollowFrame")
    assert frame.index("nameMarkBuddyPanelMoving(") < frame.index("nameMarkBuddyFollow();"), "the read comes before the frame's writes"
    assert "pm: {" in AV and "nmbFollow.pm" in _fn("nameMarkBuddyPanelMoving")
