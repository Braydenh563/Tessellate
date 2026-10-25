"""Whiteboard and mind map upgrade, agent wb2 (2026-10-25).

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/agent-remaining/wb2-1025.md`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 3]


def test_context_bar_folds_into_more_before_it_wraps():
    # The wrap check folds first, so a narrow bar stays one row (720: two rows
    # of 44px controls before, one after).
    place = _function(WB, "wbUpdateSelectionBar")
    assert place.index("wbFoldContextBar(active)") < place.index("const wrapped = active.offsetHeight > 60")
    fold = _function(WB, "wbFoldContextBar")
    # Restored on every placement, so a wider window gets the groups back.
    assert fold.index("bar.insertBefore(g") < fold.index("bar.offsetHeight <= 60")
    assert 'order: ["order", "stroke", "arrange", "caps", "route"]' in WB
    assert ".wb-context-overflow > .wb-context-group:not(.hidden)" in LAZY_CSS


def test_sketch_rotate_turns_its_selection_box_live():
    # The handle group turns about the shape's centre on every frame (the box
    # stayed upright round a shape swinging out of it), and Escape undoes it.
    handles = _function(WB, "wbDrawSketchHandles")
    assert "group.attr(\"transform\", `rotate(${currentAngle} ${centerX} ${centerY})`)" in handles
    assert 'rotateLiveD = null;\n            group.attr("transform", null);' in handles


def test_group_resize_carries_member_outlines_links_and_readout():
    multi = _function(WB, "wbRenderMultiSelectionHandles")
    assert "wbFollowMultiOutline(row.entry.item.id, newD)" in multi
    assert "if (sizeLinks.length) wbUpdateLinkedSketches(null, sizeLinks)" in multi
    assert "wbShowSizeReadout({ x: live.minX" in multi
    # The turn follows links to shapes too, not only to cards.
    assert "spinLinks = wbMultiLiveLinks(rows)" in multi
    # The follow path is dropped on save and on Escape, never left behind.
    assert "delete row.entry.item._dragLiveD" in _function(WB, "wbSaveMultiSnapshot")
    assert "delete item._dragLiveD" in _function(WB, "wbRestoreMultiSnapshot")


MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def test_map_opens_with_its_root_clear_of_the_chrome():
    # dog2 12: a remembered view that hides the root is framed instead, and a
    # new child is revealed together with its parent when the two fit.
    restore = _function(WB, "wbRestoreOrFrameBoard")
    assert "wbViewHoldsBox(saved, rootBox, free)" in restore
    assert "if (saved && rootShown && wbViewShowsContent(" in restore
    reveal = _function(MAP, "wbMapRevealTopic")
    assert "wbCenterOn(fits ? both : box" in reveal


def test_link_tool_draws_an_end_arrow_and_shows_its_ends():
    # dog2 13: the Link tool's links carried no caps (no head), and its bar
    # showed nothing; it now shares the Arrow tool's ends (default end).
    assert '"link-straight": ["ends", "head"],' in WB and '"link-curved": ["ends", "head"],' in WB
    assert "...(crossLink ? {} : wbToolCaps())," in WB


def test_zoom_to_the_selection_is_a_key_a_command_and_a_view_row():
    cmds = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    zoom = _function(WB, "wbZoomToSelection")
    assert "wbSelectionBounds()" in zoom and "refit: false" in zoom and "maxScale: 2" in zoom
    assert 'e.code === "Digit2"' in WB
    assert 'id: "zoom-selection"' in cmds and 'needs: "selection"' in cmds.split('id: "zoom-selection"')[1].split("\n")[0]
    assert 'data-wb-cmd="zoom-selection"' in html
    # Fit everything keeps its refit; the selection zoom must not inherit it.
    assert "wbFit.on = refit;" in _function(WB, "wbZoomToFit")


def test_tidy_as_a_tree_follows_the_connectors_and_shows_only_when_it_applies():
    cmds = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tidy = _function(WB, "wbTidySelection")
    # Laid out with d3.tree along the drawn direction, one move batch for Undo.
    assert "d3.tree().nodeSize([breadth, rank])" in tidy and "wbPushMoveBatch(pushed)" in tidy
    assert "!into.has(k)" in tidy  # a box no connector points into is a root
    for cmd in ("tidy-down", "tidy-right"):
        assert f'id: "{cmd}"' in cmds and 'needs: "tree"' in cmds.split(f'id: "{cmd}"')[1].split("\n")[0]
        assert html.count(f'data-wb-cmd="{cmd}"') == 2  # Arrange menu and the selection's More
    assert 'tree: () => wbTidyEdges(wbSelectionEntries()).length > 0' in cmds
    # The More section hides when no connector joins two selected items.
    assert 'more: ["more-tidy", "more-notes"]' in WB
    assert '[data-wb-ctx="more-tidy"]\')?.classList.toggle("hidden", !wbTidyEdges(' in WB
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-diagram-tools")
    assert "Tidy as a tree" in body and "Shift+2" in body


def test_change_the_shape_keeps_the_box_and_shows_only_for_a_closed_shape():
    cmds = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    change = _function(WB, "wbChangeShapeKind")
    # Drawn into the shape's present box, with the rest of its data spread in.
    assert "wbPathBBox(parsed.d)" in change and "{ ...parsed, d: swap.d(" in change
    assert 'wbPushUndo({ action: "move", kind: "sketch"' in change
    assert "WB_FILLABLE_SHAPES.has(parsed.shape)" in _function(WB, "wbSwapTarget")
    assert 'id: "change-shape"' in cmds and 'needs: "swappable"' in cmds
    assert 'data-wb-ctx="more-shape" data-wb-cmd="change-shape"' in html
    assert 'shape: { bar: ["ink", "stroke", "fill", "order"], more: ["more-link", "more-shape", "more-style"] }' in WB
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-diagram-tools")
    assert "Change the shape" in body


def test_a_shape_link_is_a_web_page_or_an_app_view_and_opens_from_its_mark():
    cmds = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # Only http(s) or a route the app opens is ever read back as a link.
    read = _function(WB, "wbItemLink")
    assert "/^https?:\\/\\//i.test(link) || routeEntry(link)" in read
    assert 'kind === "node"' in _function(WB, "wbTakesLink")  # a note card is a note already
    opener = _function(WB, "wbOpenItemLink")
    assert 'location.hash = link' in opener and '"noopener,noreferrer"' in opener
    assert "wbPaintLinkMarks();" in _function(WB, "wbPaintCommentMarks")
    assert 'id: "item-link"' in cmds and 'needs: "linkable"' in cmds
    assert 'data-wb-ctx="more-link" data-wb-cmd="item-link"' in html
    assert ".wb-link-mark {" in LAZY_CSS
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-diagram-tools")
    assert "Link…" in body


def test_text_shrinks_to_fit_a_shape_never_past_its_given_size():
    fmt = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    fit = _function(WB, "wbFitShapeLabel")
    # It starts from the size given every time, so a bigger shape gives it back.
    assert fit.index('label.style.fontSize = label.dataset.size || ""') < fit.index("let size = given")
    assert "size <= 6" in fit and "widest <= area.w" in fit
    assert "label.dataset.fit ? wbFitShapeLabel(label, area)" in _function(WB, "wbLayoutShapeLabel")
    # Only a shape takes it, so the row never shows for a text box.
    assert '"text", "fit", "geometry"' in fmt and fmt.count('"fit"') >= 2
    assert 'data-fmt="fit"' in html and 'id="wb-fmt-fit"' in html
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-diagram-tools")
    assert "shrink" in body and len(body) < 1900


def test_a_topic_dropped_between_siblings_takes_that_place():
    slot = _function(MAP, "wbMapSiblingSlotAt")
    # Only the layouts that stack siblings; Free and radial keep the drag a pin.
    assert '"tree-right": "y"' in MAP and "free" not in MAP[MAP.index("const WB_MAP_SLOT_AXIS"):MAP.index("function wbMapSiblingSlotAt")]
    assert "if (!parent || !axis) return null;" in slot
    # The place it already has is no move.
    assert "return null;\n  const gap" in slot
    drop = _function(MAP, "wbMapDropAmongSiblings")
    # It loses its pin, takes the key, and the branch is laid out again: one Undo.
    assert "pinned: _pin" in drop and "order: slot.key" in drop
    assert "wbMapTidy({ onlyBranch: wbMapTidyBranchScope(slot.parentId)" in drop
    assert drop.count("wbPushUndo(") == 1
    assert "wbMapShowSlotCue(null);" in _function(MAP, "wbMapClearDropTarget")
    # A topic under the pointer is a transplant first; Ctrl and a group drag never reorder.
    assert "d._dropTarget || d._dragAlone || d._bulkOrigin ? null : wbMapSiblingSlotAt(" in WB
    assert ".wb-map-slot-cue {" in LAZY_CSS
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "mind-maps")
    assert "between two of its siblings" in body


def test_one_branch_copies_as_an_outline_and_exports_alone():
    copy = _function(MAP, "wbMapCopyBranchOutline")
    # The server's tree, so the order and notes match the whole-map exports.
    assert "/tree`" in copy and "wbMapTreeMarkdown([node])" in copy and "copyToClipboard(" in copy
    export = _function(MAP, "wbMapExportBranch")
    assert "wbMapSubtree(index, id)" in export and "!hidden.has(o.id)" in export and "wbExportBoard();" in export
    assert 'sub("Copy this branch as an outline"' in WB and 'sub("Export this branch…"' in WB
    cmds = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'id: "copy-branch-outline"' in cmds and 'id: "export-branch"' in cmds
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "mind-map-import-export")
    assert "Copy this branch as an outline" in body and "Export this branch" in body
