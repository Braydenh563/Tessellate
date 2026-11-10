"""The owner's lag log, 2026-11-10: forced layouts in the companion, pinned by the shape that fixed each.

Reproduced at 4x CPU (Playwright, a quiet notebook, so the figures are a floor): a dialog's first
`pointerover` 7.3ms -> 0.1 to 1.4ms; the large view's open (`dblclick`) style flush 10.6 and 12.2ms
-> 0.8 to 6.4ms. Same style as tests/test_lag_forced_layout_1591.py.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MENU = (JS / "companion-menu.js").read_text(encoding="utf-8")
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
PANEL = (JS / "panel-movable.js").read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    start = source.index(head)
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(head)


def test_pointerover_does_not_measure_a_panel_inside_the_event() -> None:
    hover = PANEL[PANEL.index('document.addEventListener("pointerover"') :][:1200]
    assert "panelAdopt(p)" in hover and "afterFrames(" in hover
    assert hover.index("afterFrames(") < hover.index("panelAdopt(p)"), "the adopt reads the box, so it runs a frame on"
    assert "panelAdopt.hoverWait.has(p)" in hover, "one look waiting per panel, not one per pointerover"
    assert "panelAdopt.hoverWait = new WeakSet()" in PANEL


def test_the_visit_reads_every_limb_then_finishes_every_transition() -> None:
    body = _body(MENU, "function nameMarkBuddyVisit(")
    assert "anim.finish()" in body
    assert body.index("getComputedStyle(el).transform") < body.index("moving.push(anim)") < body.index("for (const anim of moving) anim.finish()")
    # No finish() inside the per-limb loop: that dirtied the style the next limb's read flushed.
    assert "if (anim instanceof CSSTransition) anim.finish()" not in body


def _viewer() -> str:
    start = MENU.index("function openNameMarkViewer(")
    return MENU[start : MENU.index("const NM_VIEWER_ACTS", start)]


def test_the_large_view_is_fitted_and_focused_in_the_frame_not_the_double_click() -> None:
    body = _viewer()
    assert "nameMarkViewerFit(figure);\n  requestAnimationFrame" not in body
    frame = body[body.index("requestAnimationFrame(() => {") :][:260]
    assert "nameMarkViewerFit(figure)" in frame and "close.focus()" in frame
    assert body.count("nameMarkViewerFit(figure)") == 1, "one fit, in the frame"


def test_the_pacer_reads_play_states_before_it_pauses_the_held_hands() -> None:
    body = _body(AVATARS, "function nameMarkBuddyTempo(")
    assert body.index('a.playState === "running"') < body.index("for (const a of running) a.pause()")
    assert 'if (a.playState === "running") a.pause();' not in body
