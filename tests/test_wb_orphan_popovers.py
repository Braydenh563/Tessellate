"""INBOX 1510(b): a floating bar tied to a board item closes when the item goes.

The owner, 2026-11-01: "I used these arrows to make another text box from a
note but then deleted the new one but now this floating popup toolbar is not
going away". Reproduced in the browser (agent board-1101): a quick-add arrow
on a note card opens the new card with its words selected, the selection bar
shows, and deleting the card left `#selection-bar` visible; the same for a
text box being edited. Removing a focused editor fires no `selectionchange`,
so nothing asked the bar to go. The class fix: every board render asks
`wbCloseOrphanedPopovers`, which hides an editor bar or menu whose element is
detached and closes each item popover whose item is no longer in the state.
Delete, undo, cut and a board switch all end in that render.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _function(file: str, name: str) -> str:
    source = frontend_text(file)
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _const(file: str, name: str) -> str:
    source = frontend_text(file)
    start = source.index(f"const {name} = [")
    return source[start : source.index("\n];\n", start) + 4]


def test_every_board_render_asks_once():
    render = _function("whiteboard.js", "renderWhiteboard")
    assert render.count("wbCloseOrphanedPopovers();") == 1


def test_the_popover_table_covers_the_item_popovers():
    table = _const("whiteboard.js", "WB_ITEM_POPOVERS")
    for close in ("wbCloseComments", "wbMapCloseNote", "wbMapCloseMarkers", "wbCloseMapRadial", "wbCloseMapLinkRadial"):
        assert f"{close}()" in table, close


SCRIPT = r"""
const calls = [];
const el = (connected) => ({ isConnected: connected });
global.selectionBarState = { textarea: { el: el(false) } };
global.editorMenuState = { open: true, textarea: { el: el(true) } };
global.selectionPopupField = { el: el(false) };
global.selectionBarHide = () => { calls.push("bar"); selectionBarState.textarea = null; };
global.editorCloseMenu = () => calls.push("menu");
global.hideSelectionPopup = () => calls.push("popup");
global.wbState = { objects: [{ id: 2 }], nodes: [], sketches: [] };
global.WB_LIST_BY_KIND = { object: "objects", node: "nodes", sketch: "sketches" };
global.wbCommentState = { kind: "object", id: 9 };
global.wbMapNoteState = { id: 2 };
global.wbMarkerUi = { pop: null };
global.wbMapRadialFor = null;
global.wbMapLinkRadialFor = null;
global.wbCloseComments = () => { calls.push("comments"); wbCommentState = null; };
global.wbMapCloseNote = () => calls.push("note");
global.wbMapCloseMarkers = () => calls.push("markers");
global.wbCloseMapRadial = () => calls.push("radial");
global.wbCloseMapLinkRadial = () => calls.push("linkradial");
__CODE__
wbCloseOrphanedPopovers();
const again = calls.length;
wbCloseOrphanedPopovers();
console.log(JSON.stringify({ calls, again: calls.length - again, popupField: selectionPopupField }));
"""


def test_a_gone_item_closes_its_bar_and_a_live_one_keeps_its_own():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "\n".join(
        [
            _function("editor.js", "editorSurfaceGone"),
            _function("editor.js", "editorCloseOrphans"),
            _function("whiteboard.js", "wbFindItem"),
            _const("whiteboard.js", "WB_ITEM_POPOVERS").replace("const ", "global.", 1),
            _function("whiteboard.js", "wbCloseOrphanedPopovers"),
        ]
    )
    out = subprocess.run([node, "-e", SCRIPT.replace("__CODE__", code)], capture_output=True, text=True, timeout=30, check=True)
    result = json.loads(out.stdout)
    # The detached bar and popup close; the menu on a live editor stays; the
    # comments on item 9 (gone) close, the note on item 2 (still here) stays.
    assert sorted(result["calls"]) == ["bar", "comments", "popup"]
    assert result["popupField"] is None
    # Asking again with nothing orphaned closes nothing more.
    assert result["again"] == 0
