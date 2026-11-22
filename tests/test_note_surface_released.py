"""A note editor whose box is gone is destroyed, not left on `window` (L-world-class-24).

CodeMirror's view registers `resize`, `scroll` and `selectionchange` on
`window` and `document` and removes them only in `view.destroy()`. The edit
form is rebuilt on every open, and nothing destroyed the old view, so each
note opened kept its whole editor alive: 104 listeners and 362 DOM nodes (191
KB of heap) per open, measured by `scratchpad/ui-sweeps/memiso.js` in
headless Chromium after a forced GC. Over a ten-minute loop of ordinary use
(`memrun.js`) the page went from 16,740 to 46,795 nodes and 1,240 to 5,756
listeners. A mount now first destroys every view whose editor left the page.
"""

from __future__ import annotations

from tests._app_js import documents_text

DOCS = documents_text()


def _fn(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    return DOCS[start : DOCS.index("\n}\n", start) + 2]


def test_a_mounted_view_is_remembered_so_it_can_be_released():
    assert "noteSurfaceViews.live = new Set();" in DOCS
    mount = _fn("mountNoteSurface")
    assert "noteSurfaceViews.live.add(view)" in mount


def test_views_whose_editor_left_the_page_are_destroyed_before_a_new_mount():
    mount = _fn("mountNoteSurface")
    loop = mount[mount.index("for (const gone of noteSurfaceViews.live)") : mount.index("new CM.view.EditorView")]
    assert "isConnected" in loop and "gone.destroy()" in loop and "noteSurfaceViews.live.delete(gone)" in loop
