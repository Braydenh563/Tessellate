"""INBOX 1575, a31c: the first-reader forced layouts in the lag log after a tab click.

Measured at 4x CPU on a 2,000-note notebook through a nine-tab click series: `document.getAnimations()`
from the companion's follow loop 3.9 s in all, the follow loop's panel reads 27 times inside the 400ms
`uiSettlingUntil` window (1.2 s, worst 268ms), and `atlasPlay`'s read of a box to restart a move. Each is
pinned by the shape that fixed it, in the style of tests/test_lag_forced_layout_1560.py.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    start = source.index(head)
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(head)


def test_the_follow_loop_does_not_read_while_a_page_is_arriving() -> None:
    frame = _body(AV, "function nameMarkBuddyFollowFrame(")
    hold = frame.index("window.uiSettlingUntil")
    assert hold < frame.index("nameMarkBuddyPanelMoving("), "the hold comes before the first animation read"
    assert hold < frame.index("nameMarkBuddyFollow();"), "and before the panel's box is read"
    assert "if (!settling && now >= nmbFollow.nap) {" in frame, "the reads are the ones the hold skips"
    assert "if (settling) nmbFollow.until = Math.max(nmbFollow.until," in frame, "and the loop is not ended by the wait"
    assert "requestAnimationFrame(" not in frame, "the loop is asked for through nameMarkBuddyFollowFrame.ask (a task after a drawn frame, INBOX 1766)"
    assert frame.count("nameMarkBuddyFollowFrame.ask()") == 1, "one scheduling call: the wake-source ratchet counts them"
    ask = _body(AV, "nameMarkBuddyFollowFrame.ask = function nameMarkBuddyFollowAsk(")
    assert ask.count("requestAnimationFrame(") == 1 and ask.count("setTimeout(") == 1


def test_get_animations_is_asked_only_after_something_was_set_going() -> None:
    frame = _body(AV, "function nameMarkBuddyFollowFrame(")
    assert "(nmbFollow.moving || now - nmbFollow.animAt < 2500) && nameMarkBuddyPanelMoving(" in frame
    assert "animAt: 0," in AV
    # The stamp is taken by the events that start an animation or a transition, before the panel check.
    stamp = AV.index('if (type === "transitionrun" || type === "animationstart") nmbFollow.animAt = performance.now();')
    own = AV.rindex('event.target?.closest?.("#nm-buddy")) return;', 0, stamp)
    assert stamp - own < 400, "the companion's own animations (its drawing starts them all day) do not stamp it"


def test_atlas_play_restarts_by_a_frame_not_by_a_read() -> None:
    play = _body(ATLAS, "function atlasPlay(")
    assert "getBoundingClientRect" not in play and "offsetWidth" not in play, "no forced read"
    assert "requestAnimationFrame(" not in play and "}, 2);" in play, "the class goes back two frames on (afterFrames, not a new loop)"
    assert "turns[name] !== turn" in play, "a newer play of the same move takes over from an older one"
    assert "svg.isConnected" in play
    # The class comes off at once (so the restart is a real one) and goes back inside the frames.
    assert play.index("svg.classList.remove(cls)") < play.index("afterFrames(")
    assert play.index("svg.classList.add(cls)") > play.index("afterFrames(")


def test_a_strip_wired_by_the_pointer_is_placed_by_the_observer_not_in_the_pointerover() -> None:
    shell = (ROOT / "frontend" / "js" / "shell-reminders.js").read_text(encoding="utf-8")
    glide = shell[shell.index("function glideStrip(") : shell.index("function syncEdgeFade(")]
    assert "if (!strip.glideLater) {\n    document.fonts?.ready?.then(() => place(false));\n    place(false);\n  }" in glide
    listener = glide[glide.index('for (const type of ["pointerover", "focusin"])') :]
    assert "if (strip && !strip.glide) strip.glideLater = true;" in listener
    assert listener.index("strip.glideLater = true") < listener.index("glideStrip(strip)"), "marked before it is wired"
    # The boot wiring of the top bar is not marked: it is placed at once, as before.
    assert 'glideStrip($("tab-bar"));' in shell
    assert "glideLater" not in shell[shell.index('glideStrip($("tab-bar"));') - 80 : shell.index('glideStrip($("tab-bar"));')]
