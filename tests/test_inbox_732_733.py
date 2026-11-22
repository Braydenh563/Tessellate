"""INBOX 732 and 733: the New menu's kind, the board behind it, an empty card
that stayed after its delete, and the no-model banners' close button.

The owner, 2026-10-06: "I pressed whiteboard but it selected mindmap. also when
making a new one from the library page, when I click the new button options it
opens one of my whiteboards or mindmaps in the background rather than staying
on the page I opened the create new board/mindmap panel from"; "i deleted this
empty map but itdidnt dissapear??"; and, of the Chat and Ask "No model is
connected" lines, "like an x close button or smth", back again with a new app
session.

Measured in Chromium before the fix (scratchpad `repro.js`, data dir with two
maps): pressing New, Mind map set `#wb-boards-landing` hidden and
`#wb-canvas-view` shown before the dialog had an answer, so the last board
loaded behind it, and Cancel left the canvas up. The kind was
`wbRememberedBoardKind()`, the last kind created, so Whiteboard after one map
opened on Mind map. The card that stayed was `window.wbLastCreatedBoard`,
which `drawLibraryBoardsGallery` pushes back into the list whenever the server
omits it (an empty board is not listed), and nothing cleared it on a delete.

The bodies of `createNewBoard` and `wbBinBoard` are run under node with stand-
ins for what they call.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tests._help_text import help_more_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
WB = frontend_text("whiteboard.js")
STATUS = (JS / "status.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def _node(script: str) -> dict:
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


# --- 733: New, Whiteboard / Mind map ------------------------------------------


def _new_board_run(scenario: str) -> dict:
    """`createNewBoard` with the gallery, the canvas and the create call stood
    in for. `calls` is the order things happened in."""
    body = _function(WB, "async function createNewBoard(preset = null")
    remembered = _function(WB, "function wbRememberedBoardKind() {")
    script = (
        """
const calls = [];
let remembered = "map";            // the last kind made was a map
let galleryAnswer = null;          // null is Cancel
const WB_LAST_BOARD_KIND = "wbLastBoardKind";
const prefs = { get: () => remembered };
const localStorage = { setItem() {} };
const window = {};
const toast = () => {};
const wbLibInk = () => "";
const wbLibRefBody = () => ({});
const wbZoomToFit = () => {};
const apiJson = async () => ({ id: 7, title: "t" });
const openWhiteboardBoard = async () => calls.push("open");
const wbShowCanvasView = () => calls.push("canvas");
const wbCreateBlankBoard = async (name, kind) => calls.push("create:" + kind);
async function wbOpenTemplateGallery(kind) { calls.push("gallery:" + kind); return galleryAnswer; }
"""
        + remembered
        + "\n"
        + body
        + "\n(async () => {\n"
        + scenario
        + "\nconsole.log(JSON.stringify({ calls }));\n})();\n"
    )
    return _node(script)


@needs_node
def test_whiteboard_opens_the_dialog_on_board_even_when_the_last_made_was_a_map():
    out = _new_board_run('await createNewBoard("board", { reveal: true });')
    assert out["calls"][0] == "gallery:board", out


@needs_node
def test_cancelling_the_dialog_leaves_the_page_it_was_opened_from():
    out = _new_board_run('await createNewBoard("map", { reveal: true });')
    assert out["calls"] == ["gallery:map"], out


@needs_node
def test_the_canvas_comes_up_only_once_a_name_is_chosen_and_before_the_board_is_made():
    out = _new_board_run(
        'galleryAnswer = { name: "Plan", kind: "map", ref: null };\n'
        'await createNewBoard("map", { reveal: true });'
    )
    assert out["calls"] == ["gallery:map", "canvas", "create:map"], out


@needs_node
def test_a_caller_already_on_the_canvas_does_not_reveal_it_again():
    out = _new_board_run(
        'galleryAnswer = { name: "Plan", kind: "board", ref: null };\nawait createNewBoard();'
    )
    assert out["calls"] == ["gallery:map", "create:board"], out


def test_the_library_menu_names_its_kind_and_does_not_show_the_canvas_itself():
    """New whiteboard and New mind map make an untitled one at once (Brief 77
    row 2, MINDMAP_PLAN 15 row 1); From a template is the dialog. The main New
    press and the empty tab's button bind a listener; the caret's rows (INBOX
    1520) are `kebabMenu` rows with a `run`."""
    for button, call in (
        ("wb-boards-new", "wbNewUntitledBoard()"),
        ("library-boards-new-map", 'wbNewUntitledBoard("map")'),
    ):
        start = WB.index(f'$("{button}")?.addEventListener("click"')
        line = WB[start : WB.index("\n", start)]
        assert call in line, line
        assert "wbShowCanvasView" not in line, line
    gallery = (ROOT / "frontend" / "js" / "boards-gallery.js").read_text(encoding="utf-8")
    mount = gallery[gallery.index("function wbNewMenuMount(") :]
    mount = mount[: mount.index("\n}\n")]
    # The rows wait for the board code (the arrow is up with the cards), then act.
    assert 'run: afterBoards(() => wbNewUntitledBoard("map"))' in mount
    assert 'run: afterBoards(() => wbNewUntitledBoard())' in mount
    assert 'createNewBoard("board", { reveal: true })' in mount
    assert "wbShowCanvasView" not in mount


# --- 733: the deleted empty card -------------------------------------------------


def _bin_run(scenario: str) -> dict:
    body = _function(WB, "async function wbBinBoard(id, bin) {")
    script = (
        """
const window = { wbLastCreatedBoard: { id: 5, title: "Empty map", type: "map" } };
const apiJson = async () => ({});
const refreshBoardList = async () => {};
const renderLibraryBoardsGallery = () => {};
const els = { "wb-boards-landing": { classList: { contains: () => false } } };
const $ = (id) => els[id] || null;
"""
        + body
        + "\n(async () => {\n"
        + scenario
        + "\nconsole.log(JSON.stringify({ last: window.wbLastCreatedBoard && window.wbLastCreatedBoard.id }));\n})();\n"
    )
    return _node(script)


@needs_node
def test_deleting_the_board_just_made_stops_the_gallery_drawing_it_again():
    out = _bin_run("await wbBinBoard(5, true);")
    assert out["last"] is None, out


@needs_node
def test_undoing_that_delete_brings_the_card_back():
    out = _bin_run("await wbBinBoard(5, true); await wbBinBoard(5, false);")
    assert out["last"] == 5, out


@needs_node
def test_deleting_some_other_board_leaves_the_one_just_made_alone():
    out = _bin_run("await wbBinBoard(9, true);")
    assert out["last"] == 5, out


# --- 732: the no-model banners' close ---------------------------------------------


def _notice() -> str:
    return _function(STATUS, "function renderAiOfflineNotice(")


def test_chat_ask_and_agent_banners_are_dismissible_and_the_others_are_not():
    """The agent joined Ask and Chat when it learned to run with no model
    (AGENT_SKILLS_REFORM "Deepened 2026-10-10" row 1)."""
    #: The lookups are `document.getElementById(...)` (the code moved off
    #: the `$` shorthand; the three dismissible banners are unchanged).
    block = STATUS[STATUS.index('  renderAiOfflineNotice(\n    document.getElementById("ask-offline")') : STATUS.index("  syncAgentPaletteAvailability();")]
    asks = re.search(r'getElementById\("ask-offline"\),.*?\{ dismissible: true[,}][^)]*\)', block, re.S)
    chat = re.search(r'getElementById\("chat-offline"\),.*?\{ dismissible: true[,}][^)]*\)', block, re.S)
    agent = re.search(r'getElementById\("command-palette-offline"\),.*?\{ dismissible: true[,}][^)]*\)', block, re.S)
    assert asks and chat and agent, block
    assert block.count("dismissible: true") == 3, block


def test_a_dismissed_banner_is_remembered_for_the_session_not_the_device():
    body = _notice() + _function(STATUS, "function aiOfflineDismissed(") + _function(STATUS, "function dismissAiOffline(")
    assert "sessionStorage" in body
    assert "localStorage" not in body
    assert body.count("try {") >= 2, body


def test_the_close_is_a_labelled_icon_button_on_the_dismiss_recipe():
    body = _notice()
    assert "ph:x" in body
    assert 'close.dataset.dismiss = "notice"' in body
    assert 'setAttribute("aria-label"' in body
    assert '"ghost small icon-only"' in body
    #: Last child of the row, after the text and the connect button.
    assert body.index("container.append(text, link)") < body.index("container.append(close)")


def test_the_dismiss_recipe_is_in_the_design_system():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "`data-dismiss=\"notice\"`" in design


def test_the_guide_says_the_banners_can_be_closed():
    text = help_more_text()
    assert "close button" in text and "new session" in text


def test_the_dismissal_is_written_where_the_banner_is_drawn_not_in_a_new_boot_file():
    """The boot scripts are at their gzip cap: the logic stays a few lines in
    the file that already draws the banner."""
    assert "dismissAiOffline" in STATUS
    assert not (JS / "ai-offline.js").exists()
