"""INBOX 1766: no layout read in the loops that run every frame or inside a keydown's timer.

The owner's lag log, Windows, the Documents page with a diagram open and Atlas shown:
`raf 479-1155ms atlas-motion.js atlasRigFrame` (6 to 27 calls a second, 23 growing to 130 ms a call),
`frame 210-468ms: atlasRigFrame 138-205ms (forced layout 136-203ms)`,
`avatars.js nameMarkBuddyKeepUp 110ms (forced layout 109ms)`, and
`frame 815ms: avatars.js TimerHandler:setTimeout 715ms (forced layout 685ms)` with `input 552ms keydown on body`.

A read of a style or a box inside a frame callback pays for every writer that ran since the last draw. So
the rig frame and the follow loop read nothing: the rig's reads are a task after a drawn frame
(`atlasRigWake.look`), the follow loop is itself such a task (`nameMarkBuddyFollowFrame.ask`), and a look that a
keydown or a click asks for (`nmb.afterCalm`) lets itself go rather than read a page that stays dirty.
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
JS = ROOT / "frontend" / "js"
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
AV = unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))
MENU = unwrapped((JS / "companion-menu.js").read_text(encoding="utf-8"))

#: Everything that makes the browser bring style or layout up to date.
READS = re.compile(
    r"getComputedStyle\(|getBoundingClientRect\(|getClientRects\(|getAnimations\(|checkVisibility\(|"
    r"\.offset(?:Width|Height|Top|Left)\b|\.client(?:Width|Height|Top|Left)\b|\.scroll(?:Width|Height|Top)\b|"
    r"elementFromPoint\(|\.currentTime\b|\.playState\b"
)
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, head: str) -> str:
    start = src.index(head)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(head)


def _look() -> str:
    match = re.search(r"^atlasRigWake\.look = function atlasRigLook\(.*?^\};", MOTION, re.S | re.M)
    assert match
    return match.group(0)


def _code(body: str) -> str:
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))


def test_the_rig_frame_reads_no_style_and_adds_nothing() -> None:
    frame = _code(_fn(MOTION, "function atlasRigFrame("))
    assert not READS.search(frame), READS.search(frame).group(0)
    assert "atlasRigRead(" not in frame, "the arm probes are read by atlasRigLook, after a drawn frame"
    assert not re.search(r"\.(appendChild|append|insertBefore|prepend|insertAdjacent\w+)\(", frame), "nothing is added to the page per frame"
    # What a frame appends to is bounded: the arms' quarter-second history is trimmed in the same frame,
    # and the trace is a debugging hook that is off.
    pushes = re.findall(r"(\S+)\.push\(", frame)
    assert sorted(set(pushes)) == ["arm.hist", "atlasState.rigTrace"], pushes
    assert "while (arm.hist.length > 2 && arm.hist[1][0] <= now - 200) arm.hist.shift();" in frame
    assert frame.count("if (atlasState.rigTrace) atlasState.rigTrace.push(") == pushes.count("atlasState.rigTrace")
    # The one look a frame may take is the first, at attach, before there is anything to work from.
    assert "if (!rig.reads) atlasRigWake.look(rig, true);" in frame


def test_the_rig_look_is_a_task_and_the_wake_asks_for_it_after_a_paint() -> None:
    look = _look()
    assert "atlasRigRead(" in look and "getComputedStyle(rig.pose)" in look
    assert "document.hidden" in look and "atl-off" in look, "no look in a hidden window or off screen"
    wake = _fn(MOTION, "function atlasRigWake(")
    assert "atlasRigWake.afterPaint(() => atlasRigWake.look(rig), 2)" in wake
    assert "setTimeout(atlasRigWake.look, ms, rig)" in MOTION, "the next look is a timer, never a frame callback"
    assert "requestAnimationFrame(() => atlasRigWake.look" not in MOTION


def test_the_rig_loop_stops_in_a_hidden_window_and_off_screen() -> None:
    frame = _fn(MOTION, "function atlasRigFrame(")
    assert re.search(r"if \(document\.hidden\) \{\s*rig\.at = 0;\s*rig\.dirty = true;\s*return;", frame)
    assert 'const live = atlasMotionOK(box) && !box.classList.contains("atl-off")' in frame, "off screen it does not request another frame"
    atlas = (JS / "atlas.js").read_text(encoding="utf-8")
    assert "atlasRigWake(box)" in _fn(atlas, "function atlasHiddenSync("), "the figure comes back with the window"
    assert '"atl-off"' in atlas and "IntersectionObserver" in atlas


def test_the_follow_loop_reads_in_a_task_not_a_frame_callback() -> None:
    keep = _code(_fn(AV, "function nameMarkBuddyKeepUp("))
    assert not READS.search(keep), READS.search(keep).group(0)
    assert "requestAnimationFrame(" not in keep and "nameMarkBuddyFollowFrame.ask()" in keep
    ask = _fn(AV, "nameMarkBuddyFollowFrame.ask = function nameMarkBuddyFollowAsk(")
    assert ask.index("requestAnimationFrame(") < ask.index("setTimeout("), "a frame, then a timer on: the page has drawn"
    assert ask.index("setTimeout(") < ask.index("nameMarkBuddyFollowFrame(performance.now())")
    assert "requestAnimationFrame(nameMarkBuddyFollowFrame)" not in AV
    cancel = _fn(AV, "nameMarkBuddyFollowFrame.cancel = function nameMarkBuddyFollowCancel(")
    assert "cancelAnimationFrame" in cancel and "clearTimeout" in cancel


def test_a_press_or_key_look_never_reads_a_page_that_stays_dirty() -> None:
    calm = _fn(AV, "afterCalm(fn, rounds = 4) {")
    assert "nmb.afterClean(fn, 6, function nameMarkBuddyPostpone()" in calm
    assert "fn()" not in calm.replace("afterClean(fn", ""), "the dirty branch never runs the look"
    assert "rounds > 1" in calm, "bounded: it lets the look go after the last round"
    assert "nmb.afterCalm(look)" in AV and "nmb.afterClean(look)" not in AV
    assert "nmb.afterCalm(() => nameMarkBuddyReact(kind)" in MENU, "the day's first greeting on a key"
    box = _code(_fn(AV, "nameMarkBuddyDodge.box = function nameMarkBuddyDodgeBox("))
    assert "nameMarkBuddyShape(nmb.x, nmb.y" in box, "its box is where it was put"
    assert box.count("getBoundingClientRect(") == 1 and box.index("getBoundingClientRect(") > box.index("return {"), "the rect is read only for a running walk"


def test_a_hand_over_does_not_read_a_page_written_this_instant() -> None:
    blend = _fn(AV, "function nameMarkBuddyBlend(")
    assert "nmb.written()" in blend[: blend.index("const held = [];")]
    assert "characterData: true" in AV, "a typed character dirties the page the views observer watches"
    assert "!nmb.written() && !nameMarkBuddyBehindCover() && nmbTempo.calm(now)" in AV, "and neither does the pacer's periodic look"
    written = AV[AV.index("  written: () =>") :][:120]
    assert "nmb.pageAt > 0" in written, "an unwritten page (a fresh start, a test) is not dirty"


@needs_node
def test_after_calm_runs_the_look_on_a_clean_page_and_drops_it_on_one_that_stays_dirty() -> None:
    calm = _fn(AV, "afterCalm(fn, rounds = 4) {")
    clean = re.search(r"^  afterClean\(fn, tries = 6, snap = fn, calm = 0\) \{.*?^  \},", AV, re.S | re.M).group(0)
    script = r"""
const timers = [];
let now = 0;
globalThis.performance = { now: () => now };
globalThis.window = globalThis;
globalThis.afterFrames = (f) => timers.push(f);
globalThis.setTimeout = (f, ms, ...a) => timers.push(() => f(...a));
const nmb = { pageAt: 0, lastInput: 0, __CALM__ __CLEAN__ };
globalThis.nmb = nmb;
const flush = () => { let n = 0; while (timers.length && n++ < 500) timers.shift()(); };
const out = {};
let ran = 0;
nmb.afterCalm(() => { ran += 1; });
flush();
out.clean = ran;
// A page written after every frame never goes quiet: the look is let go, not run.
ran = 0;
let writes = 0;
const orig = nmb.afterClean.bind(nmb);
nmb.afterClean = (fn, tries, snap, c) => orig(() => { writes += 1; fn(); }, tries, snap, c);
const dirtyTimers = () => { now += 5; nmb.pageAt = now + 1000; };
nmb.afterCalm(() => { ran += 1; });
let guard = 0;
while (timers.length && guard++ < 500) { dirtyTimers(); timers.shift()(); }
out.dirty = ran;
out.rounds = guard;
process.stdout.write(JSON.stringify(out));
""".replace("__CALM__", calm.replace("afterCalm(fn, rounds = 4) {", "afterCalm(fn, rounds = 4) {", 1) + ",").replace("__CLEAN__", clean.rstrip(",").replace("afterClean(", "afterClean(", 1))
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    out = json.loads(run.stdout)
    assert out["clean"] == 1, "a clean page: the look runs once"
    assert out["dirty"] == 0, "a page that stays dirty: it never reads"
    assert out["rounds"] < 400, "and it stops asking"
