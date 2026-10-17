"""The companion is never left on a perch that is gone (B88a, the owner,
2026-10-17: "the way the companion sometimes loses its perch and is left stuck
floating and not anchored to something").

Reproduced in Chromium (`scratchpad/ui-sweeps/perchloss.js`, MODE=bar, the
reminders tab, 1280x800): sitting on the status bar with its legs peeking
over it, the bar hidden by the page's own rules (on a phone the bar is
`visibility: hidden` the moment its last task ends, `10-responsive.css`)
left it in the air for good. Three holes, each with a test here that runs
the function as written in node:

- `nameMarkBuddySupported` took a peeking or leaning companion as supported
  whatever was under it, so the check that replaces a lost perch never saw
  the bar go.
- A bar holds nothing, so nothing watched it: no scroll, resize or class
  change on the body announces it going.
- A perch lost within three seconds of the last replacement was dropped by
  the rate limit, not retried, and waited for the next idle look (10 s).
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
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _const(name: str) -> str:
    return re.search(rf"^const {name} = .*;$", AV, re.M).group(0)


def _node(script: str):
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_peeking_or_leaning_companion_is_not_supported_by_a_bar_that_is_gone() -> None:
    script = "\n".join(
        [
            "const NMB_W = 64, NMB_SEAT = 60, NMB_FEET = 90, NMB_GRIP = 8;",
            _const("NMB_CANVAS"),
            "const bar = { shown: true, isConnected: true, closest: () => null };",
            "const wall = { shown: true, isConnected: true, closest: () => null };",
            "const nmb = { pose: 'sit', legs: 'peek', spot: { edge: { el: bar } }, pinned: false };",
            "const buddy = { getBoundingClientRect: () => ({ left: 600, top: 640 }) };",
            "const document = { getElementById: (id) => (id === 'nm-buddy' ? buddy : null), elementsFromPoint: () => [], documentElement: {}, body: {} };",
            "const innerWidth = 1280, innerHeight = 800;",
            "function nameMarkBuddyPerchShown(el) { return el.shown ? { top: 700, bottom: 728, left: 0, right: 1280 } : null; }",
            _fn("nameMarkBuddySupported"),
            "const out = [];",
            # Its bar there, then gone (the page hid it).
            "out.push(nameMarkBuddySupported()); bar.shown = false; out.push(nameMarkBuddySupported());",
            # Leaning on a side edge that is gone.
            "nmb.legs = ''; nmb.spot = { side: 'left', edge: { el: wall } }; wall.shown = true; out.push(nameMarkBuddySupported()); wall.shown = false; out.push(nameMarkBuddySupported());",
            # Peeking with no edge element to ask (an older saved spot): as before, not asked.
            "nmb.legs = 'peek'; nmb.spot = {}; out.push(nameMarkBuddySupported());",
            # Pinned where you put it: never asked.
            "nmb.spot = { edge: { el: bar } }; nmb.pinned = true; out.push(nameMarkBuddySupported());",
            "console.log(JSON.stringify(out));",
        ]
    )
    assert _node(script) == [True, False, True, False, True, True]


def _watch(glued: bool):
    script = "\n".join(
        [
            "const watched = []; const checks = [];",
            "class ResizeObserver { constructor(cb) { this.cb = cb; } observe(el) { watched.push(el); } disconnect() {} }",
            "const bar = { name: 'status-bar' }, card = { name: 'card', closest: () => null, parentElement: null };",
            "const nmb = { glue: " + ("{ el: card }" if glued else "null") + ", spot: { edge: { kind: 'bar', el: bar } } };",
            "const nmbFollow = { observer: null, poll: 0, frame: 0 };",
            "const document = { hidden: false, getElementById: () => null };",
            "function nameMarkBuddyTab() { return 'reminders'; }",
            "function nameMarkBuddyKeepUp() {}",
            "function nameMarkBuddyFollow() {}",
            "function queueNameMarkBuddyCheck() { checks.push(1); }",
            "const setInterval = () => 1, clearInterval = () => {};",
            _fn("nameMarkBuddyWatch"),
            "nameMarkBuddyWatch();",
            "const observers = [];",
            "console.log(JSON.stringify({ watched: watched.map((w) => w.name), barAsked: (nmbFollow.observer ? (nmbFollow.observer.cb(), checks.length) : 0) }));",
        ]
    )
    return _node(script)


@needs_node
def test_a_bar_it_sits_on_is_watched_and_its_going_asks_for_a_look_at_once() -> None:
    got = _watch(glued=False)
    assert got["watched"] == ["status-bar"], got
    assert got["barAsked"] == 1, "the bar resizing (hidden, collapsed) queues the perch check"
    # A panel it is glued to is watched by the follow loop, as before; the bar then is not.
    assert "status-bar" not in _watch(glued=True)["watched"]


def _check(since_last: int):
    script = "\n".join(
        [
            "const NOW = 1_000_000; Date.now = () => NOW;",
            "const placed = []; const timers = [];",
            "const setTimeout = (fn, ms) => { timers.push(ms); return 1; }; const clearTimeout = () => {};",
            "const performance = { now: () => 9e6 };",
            "const nmbFollow = { scrollAt: 0, recheck: 0 };",
            "const buddy = { classList: { contains: () => false } };",
            "const nmb = { pinned: false, away: false, visit: false, tab: 'reminders', glue: null, x: 100, y: 600, unheldAt: NOW - " + str(since_last) + " };",
            "const document = { getElementById: () => buddy };",
            "function nameMarkBuddyMenuOpen() { return false; }",
            "function nameMarkBuddyTab() { return 'reminders'; }",
            "function nameMarkBuddyQueuePlace() {}",
            "function nameMarkBuddySupported() { return false; }",
            "function nameMarkBuddyIndexReset() {}",
            "function placeNameMarkBuddy() { placed.push(1); }",
            "function nameMarkBuddyObstacles() { return []; }",
            "function nameMarkBuddyYoursObstacles(o) { return o; }",
            "function nameMarkBuddyHits() { return false; }",
            "function queueNameMarkBuddyCheck() {}",
            _fn("nameMarkBuddyCheck"),
            "nameMarkBuddyCheck();",
            "console.log(JSON.stringify({ placed: placed.length, timers }));",
        ]
    )
    return _node(script)


@needs_node
def test_a_perch_lost_inside_the_rate_limit_is_looked_at_again_when_it_ends() -> None:
    soon = _check(1000)
    # Lost 1 s after the last replacement: not replaced yet (no loop), but asked again
    # when the 3 s are up, not left until the next idle look 10 s on.
    assert soon["placed"] == 0 and soon["timers"] and 1900 <= soon["timers"][0] <= 2300, soon
    later = _check(5000)
    assert later["placed"] == 1, later
