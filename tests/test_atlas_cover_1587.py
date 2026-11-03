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

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AV = (JS / "avatars.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
CSS08 = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")

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
    assert {"nameMarkBuddyBeat", "nameMarkBuddyDodge", "nameMarkBuddyUnheld", "nameMarkBuddyTempo", "nameMarkBuddyTick"} <= timers
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
    start = AV.index("  afterClean(fn, tries = 6) {")
    clean = AV[start : AV.index("\n};\n", start)]
    assert "afterFrames(() => {" in clean and "setTimeout(() => {" in clean, "a timer past a frame"
    assert "nmb.pageAt > frame" in clean and "window.uiSettlingUntil" in clean
    assert "if (dirty && tries > 1) nmb.afterClean(fn, tries - 1);" in clean and "else fn();" in clean
    assert "requestAnimationFrame(" not in clean, "the file's one frame helper (the wake-source ratchet)"
    observer = AV[AV.index("const views = new MutationObserver(") :][:400]
    assert "nmb.pageAt = performance.now();" in observer
    for name in ("queueNameMarkBuddyCheck", "nameMarkBuddyBeat"):
        assert "nmb.afterClean(() => {" in _fn(AV, name), name
    assert "const afterPaint = () => nmb.afterClean(look);" in AV, "the dodge after a press"
