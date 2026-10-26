"""A resize drag moves the arrows and the links with the box, for a note card as
for a text box or picture (the owner, 2026-10-26: "the side arrows dont move
with it"). The card's drag left the four arrows on the old box until release
(measured 17px outside the box at the press, 98px inside it at +120; 22px at
every step after the fix, scratchpad/ui-sweeps/wbresize-card.js).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _block(opener: str, closer: str) -> str:
    start = SOURCE.index(opener)
    return SOURCE[start : SOURCE.index(closer, start)]


def test_card_resize_drag_updates_arrows_and_links_each_frame():
    drag = _block("  function nodeResizeDrag(handle) {", "  function nodeRotateDrag()")
    assert '_linkedSketches = wbLinkedSketchesFor(d.id, "node")' in drag
    assert "wbUpdateLinkedSketches(d.id, d._linkedSketches)" in drag
    assert "wbQueueSelectionBar()" in drag
    assert "delete d._linkedSketches" in drag


def test_object_resize_drag_updates_arrows_and_links_each_frame():
    drag = _block("  function resizeDrag(handle) {", "  function objectRotateDrag()")
    assert "wbUpdateLinkedSketches(d.id, d._linkedSketches)" in drag
    assert "wbQueueSelectionBar()" in drag
