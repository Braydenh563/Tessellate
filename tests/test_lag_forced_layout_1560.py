"""INBOX 1560, a30v: the forced layouts and the rig's rate in the owner's lag logs.

Reproduced at 4x CPU (scratchpad a30v/act.js, a click through seven tabs; idle.js, walk.js, prop.js):
`revealTab` 9 forced restyles, 1854 ms (the tab button's `tabIndex` write, while it held focus,
settled the whole arriving page); the pacer's `getAnimations` inside the arriving page's 400 ms;
a wake's first read in the click's own frame; `atlasRigFrame` at 60 calls a second; one inherited
`--nmb-ex` write on `#nm-buddy` at 113 ms for four readers. Each is pinned here by the order or
the shape that fixed it.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NAV = (JS / "navigation.js").read_text(encoding="utf-8")
AV = (JS / "avatars.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
LIFE_BOOT = (JS / "atlas.js").read_text(encoding="utf-8")
CSS08 = sheets(*FORMER_08)


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(name)


def test_the_tab_buttons_update_before_the_pages_flip() -> None:
    # A focused button's tabIndex write asks the page whether it is still focusable, which settles
    # style: after the `hidden` flips that is the whole arriving page, inside the click.
    reveal = _fn(NAV, "revealTab")
    assert reveal.index("button.tabIndex = active ? 0 : -1;") < reveal.index("classList.toggle(\"hidden\"")
    assert reveal.index("button.tabIndex = active ? 0 : -1;") < reveal.index("document.body.dataset.tab = name;")


def test_the_pacer_reads_nothing_while_a_page_is_arriving() -> None:
    tempo = _fn(AV, "nameMarkBuddyTempo")
    hold = tempo.index("if (now < (window.uiSettlingUntil || 0) && !busy) {")
    assert hold < tempo.index("nmbTempo.anims.map((anim) => anim.playState)"), "the play states are a style read"
    block = tempo[hold : tempo.index("return;", hold)]
    assert "setTimeout(nameMarkBuddyTempo" in block and "playState" not in block


def test_the_periodic_animation_look_waits_for_an_idle_moment() -> None:
    # getAnimations settles style: the 1 s look after a tab click read a still-dirty arriving page
    # (15 reads, 596 ms, max 514 ms at 4x CPU). An asked-for look (seen = 0) is still immediate.
    tempo = _fn(AV, "nameMarkBuddyTempo")
    assert "if (due && nmbTempo.seen > 0 && !nmbTempo.ready) {" in tempo
    assert "window.requestIdleCallback?.(" in tempo and "if (nmbTempo.idle === undefined) nmbTempo.ready = true;" in tempo, "no idle callback (Safari): taken on the next beat"
    assert tempo.index("} else if (due) {") < tempo.index("buddy.getAnimations(")


def test_a_wake_reads_a_frame_after_the_one_that_settled_the_page() -> None:
    assert "atlasRigWake.after = (callback, frames) => requestAnimationFrame(" in MOTION
    wake = _fn(MOTION, "atlasRigWake")
    # INBOX 1741: the first look (nothing read yet) goes one task further, after the second frame has drawn.
    assert "(rig.reads ? atlasRigWake.after : atlasRigWake.afterPaint)((now) => atlasRigFrame(rig, now), 2)" in wake and "requestAnimationFrame(" not in wake
    tail = _fn(LIFE_BOOT, "atlasTailWake")
    assert "atlasRigWake.after((now) => atlasTailFrame(tail, now), 2)" in tail


def test_the_corner_rig_draws_at_most_every_24_ms_unless_it_is_carried() -> None:
    frame = _fn(MOTION, "atlasRigFrame")
    gate = frame.index("now - rig.at < atlasRigFrame.gapMs")
    assert 'nm-buddy-dragging' in frame[gate : gate + 200], "carried, it follows the hand every frame"
    assert "buddy &&" in frame[gate - 40 : gate], "only the corner companion; the large view is drawn every frame"
    assert "atlasRigFrame.again(rig);" in frame[gate : gate + 260] and gate < frame.index("const dt =")
    assert "atlasRigFrame.gapMs = 24;" in MOTION
    assert frame.count("requestAnimationFrame(") == 1, "one frame loop"


def test_the_look_is_written_on_what_reads_it_and_does_not_inherit() -> None:
    for name in ("--nmb-ex", "--nmb-ey", "--nmb-hx"):
        assert re.search(rf'@property {name} \{{ syntax: "<number>"; inherits: false; initial-value: 0; \}}', CSS08), name
        assert f'buddy.style.setProperty("{name}"' not in AV, f"{name} is not written on #nm-buddy"
    aim = _fn(AV, "nameMarkBuddyAim")
    assert 'nameMarkBuddyAim.set(buddy, "--nmb-ex"' in aim and 'nameMarkBuddyAim.set(buddy, "--nmb-hx"' in aim
    # Every element the CSS reads the look on is in the list the writer walks.
    readers = re.search(r'nameMarkBuddyAim\.readers = "([^"]+)"', AV).group(1).split(", ")
    for selector in readers:
        assert selector in CSS08 or selector.split(" ")[-1] in CSS08, selector
    reading = [m.group(0) for m in re.finditer(r"[^\n{]*\{[^}]*var\(--nmb-(?:ex|ey|hx)\)[^}]*\}", CSS08)]
    assert reading, "the CSS reads the look somewhere"
    for rule in reading:
        head = rule.split("{")[0]
        assert any(r.split(" ")[-1] in head for r in readers), f"a reader outside the list: {head.strip()}"
