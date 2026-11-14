"""INBOX 1587, a31c: no companion timer measures the page while a modal covers it.

Reproduced at 4x CPU with Settings open and the corner Atlas on (scratchpad a31c/m.js, PROFILE=1):
the perch check, armed every 1.5 s after a press, walked every control in the open overlay
(`nameMarkBuddyFloaters` lists a shown `.modal-overlay`): 7,248 boxes in 10 s, the first read
settling the whole page, 821 ms a check. Covered, the companion is drawn at opacity 0
(`#nm-buddy[data-cover]`), so each timer that looks at the page asks `nameMarkBuddyBehindCover()`
first. The lint below finds every function avatars.js arms with `setTimeout` and holds each one
that reads layout to that order, so a new timer that reads cannot slip past it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped
from tests._css_paths import sheets

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AV = unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
CSS08 = sheets("07-whiteboard-misc.css", "characters-lazy.css")

GATE = "nameMarkBuddyBehindCover()"
#: A layout read, or a call into one of the sweeps that read a box per control.
READS = re.compile(
    r"(?:getBoundingClientRect|getClientRects|getAnimations|getComputedStyle|elementsFromPoint|elementFromPoint)\("
    r"|offset(?:Width|Height|Top|Left)|client(?:Width|Height)|scrollHeight"
    r"|nameMarkBuddy(?:Obstacles|Near|Popups|Supported|ControlsIn|ControlBoxes|Shown|StillGood|Choose|Ledges)\("
)
#: Armed by a timer, reading only what a cover cannot hide, with the reason.
EXEMPT = {
    # A resize: the window changed under it, and the ledges are two boxes.
    "nameMarkBuddyRefit": "resize",
}


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for i in range(source.index(") {", start) + 2, len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(name)


def _timer_functions() -> set[str]:
    names = set(re.findall(r"setTimeout\((nameMark\w+|nmb\w+)\b", AV))
    return {n for n in names if f"function {n}(" in AV}


def test_the_cover_is_asked_of_the_buddy_and_not_in_its_large_view() -> None:
    body = _fn(AV, "nameMarkBuddyBehindCover")
    assert 'getElementById("nm-buddy")?.dataset.cover' in body and "!nmb.visit" in body
    assert READS.search(body) is None, "the question itself reads no layout"
    assert "#nm-buddy[data-cover]:not(.nm-viewer-figure > *) {\n  opacity: 0;" in CSS08, "covered means unseen"


def test_every_timer_that_reads_the_page_asks_the_cover_first() -> None:
    timers = _timer_functions()
    assert {"nameMarkBuddyBeat", "nameMarkBuddyDodge", "nameMarkBuddyTempo", "nameMarkBuddyTick"} <= timers
    unguarded = []
    for name in sorted(timers):
        body = _fn(AV, name)
        read = READS.search(body, body.index(") {"))
        if read is None or name in EXEMPT:
            continue
        gate = body.find(GATE)
        if gate < 0 or gate > read.start():
            unguarded.append(f"{name} reads {read.group(0)} before asking the cover")
    assert not unguarded, unguarded


def test_the_queued_check_lifts_the_cover_before_it_asks() -> None:
    queue = _fn(AV, "queueNameMarkBuddyCheck")
    assert queue.index("nameMarkBuddyCoverCheck();") < queue.index(f"if (!{GATE}) nameMarkBuddyCheck();")
    check = _fn(AV, "nameMarkBuddyCheck")
    assert check.index(GATE) < check.index("nameMarkBuddyNear("), "a direct call is gated too"
    # The cover lifting queues the look that places it again.
    watch = _fn(AV, "nameMarkBuddyCoverWatch")
    assert "nmb.coverDirty = true;" in watch and "queueNameMarkBuddyCheck();" in watch


def test_the_pacer_keeps_its_list_behind_a_cover() -> None:
    tempo = _fn(AV, "nameMarkBuddyTempo")
    due = tempo.index("const due =")
    assert GATE in tempo[due : tempo.index(";", due)]


def test_a_mood_change_does_not_hand_over_a_covered_figure() -> None:
    mood = _fn(ATLAS, "setAtlasMood")
    hidden = mood.index('nameMarkBuddyBehindCover()')
    boxes = mood.index('const boxes = [...document.querySelectorAll(".atl-figure-box:not(.atl-off)")].filter((box) => !hidden?.contains(box));')
    assert hidden < boxes < mood.index("nameMarkBuddyBlend(boxes")


def test_the_blink_does_not_read_a_covered_figure() -> None:
    may = _fn(MOTION, "atlasBlinkMay")
    assert may.index(f"buddy && {GATE}") < may.index("getComputedStyle(lids)")


def test_a_look_waits_for_a_frame_that_left_the_page_clean() -> None:
    # INBOX 1591: a Library sub-tab press, rows still arriving after the frame, and the look's first
    # read laid the page out (630 ms, 486 forced). The views observer stamps a write; the look waits
    # a frame more while one landed after the last frame, six at most.
    # INBOX 1667 added `snap` (run instead of `fn` when the page is still dirty after the last try); the
    # wait-a-frame-more, six-at-most intent is unchanged.
    start = AV.index("  afterClean(fn, tries = 6, snap = fn, calm = 0) {")
    clean = AV[start : AV.index("\n};\n", start)]
    assert "afterFrames(() => {" in clean and "setTimeout(function nameMarkBuddyAfterCleanTask() {" in clean, "a named timer past a frame (INBOX 1741: an anonymous handler reads as inline in the lag log)"
    assert "nmb.pageAt > frame" in clean and "window.uiSettlingUntil" in clean
    assert "if ((dirty || moving) && tries > 1) nmb.afterClean(fn, tries - 1, snap, calm);" in clean and "else (dirty ? snap : fn)();" in clean
    assert "requestAnimationFrame(" not in clean, "the file's one frame helper (the wake-source ratchet)"
    observer = AV[AV.index("const views = new MutationObserver(") :][:400]
    assert "nmb.pageAt = performance.now();" in observer
    # INBOX 1667 (lag-1109): the check's sweep is `look`, still handed to `afterClean`; its dirty branch
    # waits for an idle frame (`wait`) instead of reading the dirty page, so the call is `afterClean(look, 6, wait)`.
    assert "nmb.afterClean(look, 6, wait);" in _fn(AV, "queueNameMarkBuddyCheck")
    assert "nmb.afterClean(() => {" in _fn(AV, "nameMarkBuddyBeat")
    assert "const afterPaint = () => nmb.afterCalm(look);" in AV, "the dodge after a press (INBOX 1766: it never reads a page that stays dirty)"


def test_the_tail_eases_home_without_reading_the_style() -> None:
    # The tail's rest beat is a timer too (`atlasTailFrame`): its hand back to the live loop read
    # `getComputedStyle(svg).transform`, a 719-element recalc of 567 ms at 1x CPU with Settings
    # open. The pose comes from the sway's own eased progress and keyframes instead.
    if not shutil.which("node"):
        pytest.skip("node not installed")
    life = unwrapped((JS / "atlas-life.js").read_text(encoding="utf-8"))
    src = "const atlasFix = (v) => +v.toFixed(2);\n" + _fn(life, "atlasTailRest") + "\n" + _fn(life, "atlasTailUnrest")
    script = r"""
const vm = require("vm");
const made = [];
const svg = { style: {}, viewBox: { baseVal: { x: 0, y: 0, width: 100, height: 100 } },
  animate: (keys, opts) => { const a = { keys, opts, cancel() { a.gone = true; }, effect: { getComputedTiming: () => ({ progress: 0.125 }) } }; made.push(a); return a; } };
const ctx = { getComputedStyle: () => { throw new Error("style read"); } };
vm.createContext(ctx);
vm.runInContext(process.argv[1], ctx);
const tail = { box: { dataset: {} }, svg, rest: [[50, 50]] };
ctx.atlasTailRest(tail, { amp: 0.4, period: 3 });
ctx.atlasTailUnrest(tail);
process.stdout.write(JSON.stringify({ sway: made[0].keys[1].transform, gone: !!made[0].gone, back: made[1].keys, live: tail.box.dataset.atlTail }));
"""
    out = subprocess.run(["node", "-e", script, src], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    deg = float(re.search(r"rotate\(([\d.]+)deg\)", got["sway"]).group(1))
    # An eighth of the swing is half way to the first keyframe: half its turn, half its swell.
    assert got["back"][0]["transform"] == f"rotate({round(deg / 2, 2):g}deg) scale(1.01)"
    assert got["back"][1] == {"transform": "none"} and got["gone"] and got["live"] == "live"
