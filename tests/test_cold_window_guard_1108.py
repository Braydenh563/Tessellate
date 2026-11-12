"""INBOX 1634 d (the owner's log, 2026-11-04): `spotNow` 5582ms, 5400 of it forced layout, 8 s after
the window came back from the tray. The first layout after a hidden web view is shown again is billed
to whatever reads first, and a throw's plan reads a world, the surfaces and the figure's box. A
release or a shake that lands before a frame has painted waits two frames (`nmb.cold`), so the page
lays itself out on the browser's own frame and the throw then reads a clean page."""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _src(name: str) -> str:
    return unwrapped((JS / name).read_text(encoding="utf-8"))


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_window_coming_back_is_cold_for_two_frames():
    js = _src("avatars.js")
    body = _body(js, "function nameMarkBuddyWarmUp(")
    assert "nmb.cold = true" in body
    assert body.count("requestAnimationFrame") == 2
    assert "nmb.cold = false" in body
    assert 'addEventListener("visibilitychange"' in js
    assert "if (!document.hidden) nameMarkBuddyWarmUp()" in js


def test_a_release_on_a_cold_window_waits_and_reads_nothing_first():
    js = _src("avatars.js")
    body = _body(js, "  const release = (event) => {")
    assert "nameMarkBuddyAfterWarm(() => drag === held && release(event))" in body
    assert body.index("nameMarkBuddyAfterWarm") < body.index("nameMarkBuddyReleaseVelocity")
    assert body.index("nameMarkBuddyAfterWarm") < body.index("nameMarkBuddyWorld(")


def test_a_shake_on_a_cold_window_is_not_a_throw():
    body = _body(_src("companion-throw.js"), "function nameMarkBuddyShaken(")
    assert "nmb.cold" in body.split("nameMarkBuddyIndexReset")[0]
