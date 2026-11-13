"""The owner, 2026-10-10: "dragging to create any object should ghost
preview that object, not be the drag selection", and a frame's drag preview
"cut off half way". The frame, sticky and text tools drew the selection
marquee's canvas; they now draw a ghost of the kind in the card layer, in
board units (`scratchpad/ui-sweeps/wbplaceghost.js`: 3/9 at 1440 before, a
marquee and no ghost for all three; 30/30 at 1440 and 1024 after)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_a_placing_drag_draws_a_ghost_not_the_marquee():
    assert "if (wbMarqueeStart.place) wbBeginPlaceGhost(wbMarqueeStart.pointerId, wbMarqueeStart.place);" in WB
    body = WB[WB.index("function wbBeginPlaceGhost("):]
    body = body[:body.index("\n  }\n")]
    assert 'getElementById("wb-html-layer")' in body
    #: The capture goes through the one helper (L271), which calls setPointerCapture.
    assert "wbBoardState.capture(containerEl, pointerId)" in body
    assert "el.setPointerCapture(pointerId)" in WB


def test_each_kind_has_its_look():
    for kind in ("frame", "sticky", "text"):
        assert f'.wb-place-ghost[data-kind="{kind}"]' in LAZY
    assert "--wb-sticky-paper" in LAZY
