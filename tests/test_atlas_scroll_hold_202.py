"""Source text: the hold is lifted from the script text and run in node's vm, as the unit suite has no browser to scroll; the browser numbers are in companioncpu.js.

L-ui-modernisation-202: Atlas's loops are held while the page scrolls.

companioncpu.js (RUNS=5, full figure, no throttle) put each scroll step at 10 to 11 ms more with Atlas shown: every
scroll frame restyled the figure's running loops (shimmer, skirt, nebula drift, rings, orbiters) and the morph's
repaints rode it. A wheel or a touch drag pauses every running loop that never ends (`pause()`, so each keeps its
phase and nothing jumps on resume) and the morph draws nothing; `scrollend`, or a quiet spell where it never fires,
plays back exactly the ones the hold paused. Fixed clock, fakes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i : src.index(end, i)]


HARNESS = r"""
let clock = 0;
const timers = [];
const setTimeout = (fn, ms) => { timers.push({ fn, at: clock + ms, id: timers.length + 1 }); return timers.length; };
const clearTimeout = (id) => { const t = timers.find((x) => x.id === id); if (t) t.fn = null; };
const advance = (ms) => {
  const end = clock + ms;
  for (;;) {
    const due = timers.filter((t) => t.fn && t.at <= end).sort((a, b) => a.at - b.at)[0];
    if (!due) break;
    clock = due.at;
    const fn = due.fn;
    due.fn = null;
    fn();
  }
  clock = end;
};
const listeners = {};
const anim = (name, iterations, state = "running") => ({
  name, playState: state, calls: [],
  effect: { getComputedTiming: () => ({ iterations }) },
  pause() { this.calls.push("pause"); this.playState = "paused"; },
  play() { this.calls.push("play"); this.playState = "running"; },
  cancel() { this.calls.push("cancel"); this.playState = "idle"; },
});
const loops = [anim("shimmer", Infinity), anim("skirt", Infinity), anim("blink", 1), anim("rested", Infinity, "paused")];
let shown = true;
const document = {
  addEventListener: (type, fn, opts) => { (listeners[type] ||= []).push({ fn, capture: opts === true || !!opts?.capture }); },
  getElementById: (id) => (id === "nm-buddy" && shown ? { getAnimations: (o) => (o?.subtree ? loops : []), querySelectorAll: (q) => (q === ".atl-figure-box" ? ["box"] : []) } : null),
};
const woke = [];
const atlasRigWake = (box) => woke.push(box);
const fire = (type) => (listeners[type] || []).forEach((l) => l.fn({ type }));
const atlasTailCalm = () => {};
const atlasRigFrame = () => {};
"""


def _run(body: str) -> dict:
    code = HARNESS + _block(LIFE, "atlasTailCalm.scroll = {", "//: End of the scroll hold.") + body
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout)


def _states() -> str:
    return "Object.fromEntries(loops.map((a) => [a.name, a.playState + ':' + a.calls.join(',')]))"


@needs_node
def test_a_wheel_pauses_the_running_endless_loops_and_scrollend_plays_them_back() -> None:
    got = _run(
        f"""
fire("wheel");
const before = {_states()};
advance(1);
const held = {_states()};
const on = atlasTailCalm.scroll.on;
advance(50); fire("scroll"); advance(50); fire("scroll");
const wokeHeld = woke.length;
const rigHeld = atlasRigFrame.held;
fire("scrollend");
process.stdout.write(JSON.stringify({{ before, held, on, after: {_states()}, off: atlasTailCalm.scroll.on, wokeHeld, woke, rigHeld, rigAfter: atlasRigFrame.held }}));
"""
    )
    # Collected after the input's own task (the rest's wake runs first), never in the event.
    assert got["before"]["shimmer"] == "running:"
    assert got["on"] is True
    assert got["held"] == {"shimmer": "paused:pause", "skirt": "paused:pause", "blink": "running:", "rested": "paused:"}
    # Played back once, the finite blink never touched, the one paused by someone else left paused.
    assert got["after"] == {"shimmer": "running:pause,play", "skirt": "running:pause,play", "blink": "running:", "rested": "paused:"}
    assert got["off"] is False
    # The tail's and the rig's frames, stopped while held, are woken once at the end.
    assert got["wokeHeld"] == 0 and got["woke"] == ["box"]
    assert got["rigHeld"] is True and got["rigAfter"] is False


@needs_node
def test_without_scrollend_a_quiet_spell_resumes_and_each_scroll_rearms_it() -> None:
    got = _run(
        f"""
fire("touchmove");
advance(1);
const quiet = atlasTailCalm.scroll.quiet;
for (let i = 0; i < 10; i += 1) {{ advance(quiet - 20); fire("scroll"); }}
const still = {_states()}.shimmer;
advance(quiet + 1);
process.stdout.write(JSON.stringify({{ quiet, still, after: {_states()}.shimmer, on: atlasTailCalm.scroll.on }}));
"""
    )
    assert 100 <= got["quiet"] <= 300
    assert got["still"] == "paused:pause", "a scroll inside the quiet spell must keep the hold"
    assert got["after"] == "running:pause,play" and got["on"] is False


@needs_node
def test_a_scroll_without_a_wheel_or_touch_holds_nothing() -> None:
    """A program's scroll (the chat following a streamed answer) is not the reader's: the figure keeps moving."""
    got = _run(
        f"""
fire("scroll"); advance(5); fire("scrollend"); advance(1000);
process.stdout.write(JSON.stringify({{ s: {_states()}, on: atlasTailCalm.scroll.on }}));
"""
    )
    assert got["s"]["shimmer"] == "running:" and got["on"] is False


@needs_node
def test_no_companion_holds_nothing_and_a_second_wheel_collects_once() -> None:
    got = _run(
        f"""
shown = false; fire("wheel"); advance(1);
const none = atlasTailCalm.scroll.on;
advance(1000); shown = true;
fire("wheel"); advance(1); fire("wheel"); advance(1); fire("scroll");
const once = {_states()}.shimmer;
fire("scrollend");
process.stdout.write(JSON.stringify({{ none, once, after: {_states()}.shimmer }}));
"""
    )
    assert got["none"] is False
    assert got["once"] == "paused:pause"
    assert got["after"] == "running:pause,play"


def test_the_listeners_are_passive_captures_and_pause_keeps_the_phase() -> None:
    block = _block(LIFE, "atlasTailCalm.scroll = {", "//: End of the scroll hold.")
    for type_ in ('"wheel"', '"touchmove"', '"scroll"', '"scrollend"'):
        assert type_ in block, type_
    assert "passive: true" in block and "capture: true" in block
    # pause() and play() keep each loop's time; a cancel or a restart would jump the figure.
    assert ".cancel()" not in block and "currentTime" not in block


def test_the_morph_draws_nothing_while_the_page_scrolls() -> None:
    run = LIFE[LIFE.index("atlasRigLower.morph.run = ") :]
    run = run[: run.index("\n  };\n", run.index("const step = "))]
    assert "atlasTailCalm.scroll.on" in run
    # The clock does not run on while held, so the shapes take up where they stopped.
    hold = run[run.index("atlasTailCalm.scroll.on") :]
    assert "m.at = 0" in hold[: hold.index("return;")]


def test_the_tail_and_the_rig_frames_stop_while_the_companion_is_held() -> None:
    tail = _block(LIFE, "function atlasTailFrame(", "if (live) atlasFrameBudget(now);")
    assert 'atlasTailCalm.scroll.on && box.closest("#nm-buddy")' in tail and "tail.at = 0;" in tail
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    rig = _block(motion, "function atlasRigFrame(", "const live = atlasMotionOK(box)")
    assert 'atlasRigFrame.held && rig.host?.id === "nm-buddy"' in rig and "rig.dirty = true" in rig
    hold = _block(LIFE, "atlasTailCalm.scroll = {", "//: End of the scroll hold.")
    assert "atlasRigFrame.held = true" in hold and "atlasRigFrame.held = false" in hold
    # The HTML-box loops' once-a-second sync must not play them back mid-scroll.
    sync = LIFE[LIFE.index("box.atlasLoopsOn !== loops") - 200 : LIFE.index("box.atlasLoopsOn !== loops")]
    assert "!atlasTailCalm.scroll.on" in sync
