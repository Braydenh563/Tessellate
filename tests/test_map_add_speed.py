"""Adding a topic answers in one frame's work, not after the server and two
whole-map renders (audit FEAT-02, 2026-10-05), and the small faults the same
audit found on the add path (FEAT-15, FEAT-16).

The latency itself is measured in a browser
(`scratchpad/ui-sweeps/mmdoc1005-mapaddlatency.js`, key to an editable topic
at 6, 101 and 301 topics); these pin the shape that makes it fast, so a later
change that puts the network or a second render back on the path fails here
rather than being noticed as "the map is slow again".
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = frontend_text("whiteboard-map.js") + frontend_text("whiteboard-map-record.js")  # L-whiteboard-49: the Undo-recorded commands moved to whiteboard-map-record.js
WB_JS = frontend_text("whiteboard.js")


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.index("\n}\n", start)
    return source[start:end]


def test_the_add_opens_the_editor_before_the_server_answers():
    body = _body(MAP_JS, "async function wbMapAddChild(")
    # The editor opens in the add itself; the POST lives in the adoption.
    assert "wbMapEditNode(created.id, { now: true })" in body
    assert "apiJson(" not in body
    assert body.index("wbMapEditNode(created.id") < body.index("wbMapAdoptProvisional(")
    #: The moves and the lines wait for the editor (FEAT-02's 100ms gate).
    assert body.index("wbAddGate.renderHold = {") < body.index("renderWhiteboardNow()") < body.index("wbRenderRelease()")
    adopt = _body(MAP_JS, "async function wbMapAdoptProvisional(")
    assert "/nodes`" in adopt and "wbRemapUndoIds(" in adopt


def test_the_add_renders_the_map_once():
    body = _body(MAP_JS, "async function wbMapAddChild(")
    assert body.count("renderWhiteboardNow()") == 1
    # No whole-map tidy (it renders and waits for its save) on the add path.
    assert "await wbMapTidyBranch(" not in body
    assert "wbMapTidyBranchPlan(" in body


def test_a_move_is_a_transform_not_a_repaint():
    """The paint key leaves out x and y, so a tidy that shifts most of the
    map writes transforms (measured: 409ms of setAttribute in one Tab at 301
    topics while every moved topic was repainted)."""
    key = _body(WB_JS, "function wbObjectPaintKey(")
    base = re.search(r"const base = `([^`]*)`", key).group(1)
    assert "d.x" not in base and "d.y" not in base
    update = WB_JS[WB_JS.index("const key = wbObjectPaintKey(d, paintCtx);"):][:600]
    assert "movesLater.push([this, place])" in update
    #: Written after the measure, so the measure restyles only what repainted.
    tail = WB_JS[WB_JS.index("objectUpdate.each(function (d) {\n      if (!WB_MAP_KINDS.has(d.kind)) return;"):][:1600]
    assert tail.index("this.offsetHeight") < tail.index("el.style.transform = place")


def test_a_save_waits_for_a_provisional_topic():
    save = _body(WB_JS, "async function wbSaveObject(")
    assert "d._creating" in save


def test_a_new_topic_and_its_first_name_are_one_undo_step():
    """FEAT-15: five Ctrl+Z took 101 topics to 99, two steps a topic."""
    assert "live._fresh" in MAP_JS
    assert "_fresh: true" in _body(MAP_JS, "async function wbMapAddChild(")


def test_a_committed_name_returns_focus_to_the_canvas_and_is_announced():
    """FEAT-16: after a name was committed, focus sat on <body>."""
    start = MAP_JS.index('text.on("blur", function () {')
    blur = MAP_JS[start:start + 3000]
    assert 'getElementById("whiteboard-container")?.focus(' in blur
    assert "wbAnnounce(" in blur


def test_the_render_skips_the_search_highlight_walk_when_no_search_is_live():
    # L-mindmap-13: every render walked every object to toggle two classes off.
    body = _body(WB_JS, "function wbApplySearchHighlight(")
    guard = body.index("document.querySelector(\".wb-search-hit, .wb-search-current\")")
    assert "!wbBoardSearch.matches.length" in body[:guard + 120]
    assert guard < body.index("querySelectorAll(")
