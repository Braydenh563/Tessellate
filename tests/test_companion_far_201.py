"""Source text: the pointer check is lifted from the script text and run in node's vm, and the CSS rule is read as text, as the unit suite has no browser to hit-test.

L-ui-modernisation-201: the companion is hit-tested only while the mouse is near it.

After every frame that lays out, Blink hit-tests the page at the pointer (hover and the cursor), and a wheel hit-tests
its target; over the companion's hundred layers each test cost. cpuab A/B (RUNS=3, pointer still over the page):
idle 141 to 125 ms/s and a wheel step 5.70 to 4.03 ms with the companion out of hit testing. So a mouse further than
`farPx` from its box marks it `data-nmb-far` (characters-lazy.css: no pointer events), and a mouse near it, a touch or
a pen, an open menu or a ride clears it. Looked at on each move (a mouse's come once a frame) from `nmb` alone, and
written only on a change. Fakes, no clock.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i : src.index(end, i)]


HARNESS = r"""
const attrs = new Set();
let writes = 0;
const buddy = { hasAttribute: (k) => attrs.has(k), toggleAttribute: (k, on) => { writes += 1; return on ? attrs.add(k) : attrs.delete(k); } };
let shown = true, menu = false;
const document = { getElementById: (id) => (id === "nm-buddy" && shown ? buddy : null), addEventListener: () => {} };
const nameMarkBuddyMenuOpen = () => menu;
const NMB_W = 64, NMB_H = 92;
const nmb = { x: 1284, y: 774, scale: 1, pointer: null, mouse: true };
function nameMarkBuddyPointer() {}
"""


def _run(body: str) -> dict:
    code = HARNESS + _block(AV, "nameMarkBuddyPointer.farPx = ", "//: End of the far hit test.") + body
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout)


@needs_node
def test_far_is_outside_the_box_and_its_margin_and_never_without_a_place_a_ride_or_with_a_menu() -> None:
    got = _run(
        r"""
const F = nameMarkBuddyPointer.away, m = nameMarkBuddyPointer.farPx;
const out = {
  m,
  corner: F(400, 300),
  inside: F(1300, 800),
  edge: F(1284 - m + 1, 800),
  beyond: F(1284 - m - 1, 800),
  below: F(1300, 774 + 92 + m + 1),
};
nmb.scale = 2; out.scaled = F(1284 + 64 * 2 + m - 1, 800); nmb.scale = 1;
nmb.ride = { el: {} }; out.riding = F(400, 300); nmb.ride = null;
menu = true; out.menu = F(400, 300); menu = false;
nmb.x = NaN; out.unplaced = F(400, 300); nmb.x = 1284;
nmb.away = true; out.away = F(400, 300);
process.stdout.write(JSON.stringify(out));
"""
    )
    assert 16 <= got["m"] <= 48
    assert got["corner"] is True and got["beyond"] is True and got["below"] is True and got["away"] is True
    assert got["inside"] is False and got["edge"] is False and got["scaled"] is False
    assert got["riding"] is False and got["menu"] is False and got["unplaced"] is False


@needs_node
def test_a_move_writes_only_when_far_changes_and_a_touch_never_marks_it() -> None:
    got = _run(
        r"""
const out = {};
nmb.pointer = [400, 300];
for (let i = 0; i < 12; i += 1) { nmb.pointer = [400 + i, 300]; nameMarkBuddyPointer.mark(); }
out.writes = writes;
out.far = attrs.has("data-nmb-far");
nmb.pointer = [1300, 800]; nameMarkBuddyPointer.mark();
out.near = attrs.has("data-nmb-far");
nmb.pointer = [400, 300]; nameMarkBuddyPointer.mark();
nmb.mouse = false; nameMarkBuddyPointer.mark();
out.touch = attrs.has("data-nmb-far");
out.total = writes;
shown = false; nmb.mouse = true; nameMarkBuddyPointer.mark();
process.stdout.write(JSON.stringify(out));
"""
    )
    assert got["writes"] == 1, "twelve far moves restyle the companion once"
    assert got["far"] is True and got["near"] is False and got["touch"] is False
    assert got["total"] == 4


def test_the_pointer_listeners_and_the_companions_place_look_again() -> None:
    move = _block(AV, 'document.addEventListener("pointermove", (event) => {\n    nmb.pointer = ', "}, { passive: true });")
    assert 'nmb.mouse = event.pointerType === "mouse"' in move and "nameMarkBuddyPointer.mark()" in move
    put = _block(AV, "function nameMarkBuddyPut(", "\n  }\n")
    assert "nameMarkBuddyPointer.mark()" in put, "a companion that moves under a still mouse must be hit-testable again"
    far = _block(AV, "nameMarkBuddyPointer.farPx = ", "//: End of the far hit test.")
    assert '"pointerdown"' in far and 'pointerType !== "mouse"' in far
    assert "getBoundingClientRect" not in far and "elementFromPoint" not in far
    assert "requestAnimationFrame" not in far, "no new frame loop (test_frontend_wake_sources.py)"


def test_the_css_takes_every_part_out_of_hit_testing_the_grip_included() -> None:
    rule = re.search(r"(?:(?<=[{}])|\A)([^{}]*#nm-buddy\[data-nmb-far\][^{}]*)\{([^}]*)\}", CSS)
    assert rule, "characters-lazy.css needs the data-nmb-far rule"
    sel, body = rule.group(1), rule.group(2)
    assert "pointer-events: none" in body and "!important" not in body
    assert "#nm-buddy[data-nmb-far] *" in sel
    # The size grip's `pointer-events: auto` and the standing or sitting handle (the face's ::after, which `*` does
    # not match) must both lose to it: each is an id, an attribute or two and a class.
    assert ".nmb-size-grip" in sel and ".nm-buddy-face::after" in sel
    assert sel.count(":is([data-pose])") >= 2, "outranks the pose rules without !important"
