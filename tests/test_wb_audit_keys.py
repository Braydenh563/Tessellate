"""The board's and the map's keys, as the INBOX 445 audit found them.

Four keys did two things or the wrong thing, each measured by driving the
real UI (`scratchpad/ui-sweeps/wbaudit.js`):

* M picked the highlighter *and* armed the app's "m" quick-nav chord, so the
  chord guide opened over the canvas, took the stroke's pointerup (the stroke
  was never saved), and the next tool letter was read as a destination.
* On a map, the letters of the board-only tools (R, P, M, T...) still picked
  those hidden tools, and I still pressed the hidden picture button.
* Escape inside a text box or sticky was stopped with every other key, so
  the caret stayed in the box and the next tool letter was typed into it.

These read the source because the behaviour lives in two listeners on
`document` in two files, and what has to hold is the handoff between them.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
WIRING = (JS / "settings-wiring.js").read_text(encoding="utf-8")


def _function_body(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    depth = 0
    # The body's brace, not a destructured parameter's (`{ above = false } = {}`).
    for i in range(src.index(") {", start) + 2, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise AssertionError(f"{name} has no closing brace")


def test_board_owns_bare_m_but_a_map_does_not():
    body = _function_body(WB, "wbOwnsChord")
    # C23: bare T (text tool) steps aside the same way as bare M.
    assert '["m", "t"].includes(e.key.toLowerCase())' in body
    assert "wbIsMap()" in body


def test_the_m_chord_steps_aside_for_the_board():
    arm = WIRING[WIRING.index('singleKeys && (e.key === "m" || e.key === "t")') - 200 :]
    arm = arm[: arm.index("showTabJumpHint()")]
    assert "!boardOwns" in arm and "const boardOwns = typeof wbOwnsChord" in WIRING


def test_a_map_never_picks_a_board_only_tool_by_key():
    dispatch = WB[WB.index("const mapped = (e.shiftKey && WB_TOOL_SHIFT_KEYS[letter])") :]
    dispatch = dispatch[: dispatch.index("selectWbTool(mapped)")]
    assert re.search(r"wbIsMap\(\)\s*&&\s*WB_BOARD_ONLY_TOOLS\.has\(mapped\)", dispatch)


def test_a_map_never_presses_a_board_only_action_key():
    block = WB[WB.index("if (WB_ACTION_KEYS[letter]) {") :][:600]
    assert 'data-wb-surface="board"' in block and "wbIsMap()" in block


def test_escape_leaves_a_text_box_selected_rather_than_typing_on():
    start = WB.index('content.on("keydown", function (event) {')
    handler = WB[start : WB.index('content.on("pointerdown"', start)]
    esc = handler[handler.index('event.key === "Escape"') :]
    assert esc.index("this.blur()") < esc.index("return;")
    assert 'selectWbItem("object", d.id)' in esc


MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")


def test_siblings_sort_by_their_order_key_and_colours_by_creation():
    index = _function_body(MAP, "wbMapIndex")
    assert "list.sort(wbMapBySiblingOrder)" in index and "roots.sort(wbMapBySiblingOrder)" in index
    key = _function_body(MAP, "wbMapOrderKey")
    assert "data?.order" in key and "obj.id" in key
    # A branch keeps its colour when it moves: the palette walks by id.
    assert "sort((a, b) => a.id - b.id)" in _function_body(MAP, "wbMapColors")


def test_ctrl_shift_arrows_move_a_topic_and_enter_inserts_in_place():
    assert "wbMapMoveAmongSiblings(mapNode.id" in WB
    assert "wbMapAddSibling(mapNode.id, { above: e.shiftKey })" in WB
    move = _function_body(MAP, "wbMapMoveAmongSiblings")
    assert "wbPushUndo" in move and "wbMapTidyBranch" in move
    assert "wbMapKeyBetween" in _function_body(MAP, "wbMapAddSibling")


def test_deleting_a_map_branch_is_on_the_undo_stack():
    delete = _function_body(MAP, "wbMapDeleteSubtree")
    assert 'action: "subtree"' in delete and "wbPushUndo(entry)" in delete
    history = _function_body(WB, "wbApplyHistoryEntry")
    assert 'entry.action === "subtree"' in history and 'entry.action === "unsubtree"' in history
    # The restore writes the whole row back, not only the text and colour.
    assert 'method: "PUT"' in _function_body(MAP, "wbMapRestoreRows")


def test_the_undo_stack_is_a_hundred_deep():
    depth = int(re.search(r"const WB_UNDO_MAX = (\d+);", WB).group(1))
    assert depth >= 100


HTML = (JS.parent / "index.html").read_text(encoding="utf-8")


def test_the_tool_bar_shows_only_what_the_held_tool_reads():
    table = WB[WB.index("const WB_TOOL_SETTINGS = {") :]
    table = table[: table.index("};")]
    # The eraser, the sticky, the text box and the bucket read none. The Link
    # tool reads its ends since it draws an end arrow (wb2, 2026-10-25).
    for tool in ("eraser", "sticky", "text", "bucket"):
        assert f"{tool}:" not in table and f'"{tool}"' not in table
    assert '"link-straight": ["ends", "head"]' in table
    assert 'draw: ["size", "dash"]' in table
    for setting in ("size", "ends", "dash", "fill"):
        assert f'data-wb-tool-setting="{setting}"' in HTML
    assert "wbHideSelectionActions(" in _function_body(WB, "wbFillContextBar")


def test_the_fill_switch_means_filled_when_on():
    assert 'id="wb-fill-none"' not in HTML
    assert 'id="wb-fill-on"' in HTML
    assert "window.currentFillNone = !e.target.checked" in WB


def test_a_board_canvas_is_a_tab_stop_whose_tab_walks_the_items():
    tag = HTML[HTML.index('id="whiteboard-container"') - 60 :][:400]
    assert 'tabindex="0"' in tag and 'role="application"' in tag
    assert 'id="wb-announcer"' in HTML
    assert "wbWalkItems(e.shiftKey ? -1 : 1)" in WB
    walk = _function_body(WB, "wbWalkItems")
    # Past the end the key is left to the browser: no keyboard trap.
    assert "if (next < 0 || next >= items.length) return false;" in walk
    assert "wbAnnounce(" in walk
    # Select all takes pictures too.
    assert "wbSelectableItems()" in _function_body(WB, "wbSelectAllItems")


def test_keys_typed_before_a_new_topics_editor_opens_are_kept():
    assert "wbMapCatchTypeahead(e)" in WB
    owns = _function_body(WB, "wbOwnsChord")
    assert owns.index("wbMapTypeaheadLive()") < owns.index('["m", "t"]')
    assert "boardOwns" in WIRING
    edit = _function_body(MAP, "wbMapEditNode")
    assert "wbMapTypeahead = null" in edit and "el.textContent = typed" in edit


def test_an_enter_typed_ahead_ends_the_name_rather_than_adding_a_sibling():
    # Tab, a name and Enter at speed saved two empty topics (2026-10-04): the
    # Enter reached the map's own Enter before the editor opened. It is held
    # as a commit, and the editor closes on the typed text when it opens.
    catch = _function_body(MAP, "wbMapCatchTypeahead")
    assert catch.index('e.key === "Enter"') < catch.index("e.key.length !== 1")
    assert "wbMapTypeahead.commit = true" in catch
    edit = _function_body(MAP, "wbMapEditNode")
    assert "wbMapTypeahead?.commit" in edit and "if (commit) el.blur()" in edit


def test_a_drag_measures_nothing_it_does_not_have_to():
    # The cull reads the gesture's cached canvas box, not clientWidth.
    assert "wbCullNow(undefined, rect ?" in _function_body(WB, "wbScheduleCull")
    # "Found none" is cached too.
    chrome = _function_body(WB, "wbTranslateSelectionChrome")
    assert "if (!groups || groups.some(" in chrome
    # A group drag's bar rides on the box at the start plus the delta.
    bar = _function_body(WB, "wbUpdateSelectionBar")
    assert "wbBulkBarBounds" in bar and "barMeasure" in bar
    assert "entry.pathEl" in _function_body(WB, "wbApplyBulkMove")


# --- INBOX 445 (2), found not fixed: five undo and key gaps on a map ----------


def test_a_restored_branch_gets_its_cross_links_back_between_the_new_topics():
    delete = _function_body(MAP, "wbMapDeleteSubtree")
    assert "res.links" in delete and "links }" in delete
    restore = _function_body(MAP, "wbMapRestoreRows")
    # Ends inside the branch are translated, and the link is written again.
    assert "remap.get(data[idKey])" in restore and '"/whiteboard/sketches"' in restore
    history = _function_body(WB, "wbApplyHistoryEntry")
    assert "wbMapRestoreRows(entry.rows, entry.links" in history
    # Redo carries the links on the entry it builds, so a second Undo has them.
    assert 'action: "subtree", kind: "object", rows, links' in history


def test_a_restore_rewrites_the_ids_older_history_entries_name():
    restore = _function_body(MAP, "wbMapRestoreRows")
    assert "wbRemapUndoIds(remap, linkRemap)" in restore
    remap = _function_body(WB, "wbRemapUndoIds")
    # Both stacks, batches, the reparent target and a link's two ends.
    assert "wbUndoStack.forEach(walk)" in remap and "wbRedoStack.forEach(walk)" in remap
    for needle in ("entry.entries.forEach(walk)", "entry.parentId", "entry.ids", "row.parent_id", "data.${field}", "sourceId", "targetId"):
        assert needle in remap


def test_shift_tab_is_one_undo_step():
    outdent = _function_body(MAP, "wbMapOutdent")
    assert 'action: "reparent"' in outdent and "wbPushUndo(" in outdent
    # The tidy that follows moves topics, so their places ride in the same step.
    assert 'action: "move"' in outdent and 'action: "batch"' in outdent


def test_undoing_a_create_selects_the_parent():
    undo = _function_body(WB, "wbUndo")
    assert "wbUndoParents" in undo and 'selectWbItem("object", parentId)' in undo
    history = _function_body(WB, "wbApplyHistoryEntry")
    assert "wbUndoParents.push(item.parent_id)" in history


def test_tab_adds_a_topic_only_when_the_map_was_engaged_and_focus_is_on_it():
    assert "let wbMapKeysArmed = false;" in WB
    gate = WB.index("if (!wbMapKeysArmed || !onMap) return;")
    # Not armed, or focus on another control: return before preventDefault, so
    # the browser's own Tab runs.
    assert WB[gate:].index("e.preventDefault();") < WB[gate:].index("wbMapOutdent(mapNode.id)")
    assert WB[gate - 900 : gate].rindex('e.key === "Tab"') > 0
    # A press on the canvas arms it, focus arriving from another control disarms.
    assert "wbMapKeysArmed = true;" in WB[WB.index("// A press on the map is the strongest way") :][:400]
    assert "wbMapKeysArmed = false;" in WB[WB.index("//: **Focus landing on any control outside the canvas") :][:900]
    assert "if (wbIsMap()) wbMapKeysArmed = true;" in _function_body(WB, "selectWbItem")


def test_focus_mode_reads_the_cross_links_by_the_names_the_server_sends():
    near = _function_body(MAP, "wbMapFocusHidden")
    assert "link.from_id" in near and "link.to_id" in near
    assert "source_id" not in near and "target_id" not in near


# --- 2026-10-04: the connect drag's cue, and a menu row that threw -----------


def test_a_connect_drag_says_which_connection_it_will_make_in_flight():
    # MINDMAP_PLAN 13c's remainder. One decision for the cue and the drop, so
    # the cue cannot promise one kind and the release make the other.
    join = _function_body(MAP, "wbMapJoinByLink")
    assert "wbMapJoinPlan(source, target)" in join
    cue = _function_body(MAP, "wbMapLinkCue")
    assert "wbMapJoinPlan(source, target)" in cue and "wbAnnounce(" in cue
    drag = _function_body(WB, "dragging")
    assert "wbMapLinkCue(d, hover ? hover[1] : null)" in drag
    assert "wb-link-preview-crosslink" in drag
    # Released, taken back by Escape: the cue goes either way.
    assert "wbMapClearLinkCue()" in _function_body(WB, "dragEndNode")


def test_nothing_outside_the_boards_setup_calls_its_private_tool_picker():
    # `selectWbTool` is declared inside `initWhiteboard`; a top-level function
    # that calls it by name throws (the topic menu's "Connect this topic to
    # another" did, 2026-10-04). Outside, the handle is `wbSelectToolRef`.
    init = _function_body(WB, "initWhiteboard")
    code = re.sub(r"(?m)^\s*//.*$", "", WB)
    inside = len(re.findall(r"\bselectWbTool\(", re.sub(r"(?m)^\s*//.*$", "", init)))
    assert len(re.findall(r"\bselectWbTool\(", code)) == inside
