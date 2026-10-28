"""A mind-map topic's controls: on the topic and on its bar, two presses at most.

INBOX 610 (the owner: resizing a topic, resizing its text and changing its
other features "with the individual nodes themselves and the popup tool
menus" was "unintuitive"). Measured by `scratchpad/ui-sweeps/
bm1005-nodetasks.js` on the base: 8 of 11 topic properties could not be set
in two presses (each was a select inside a door), the two grips floated above
the topic's top left and dragging "Aa" upwards made the text smaller. After:
every task in at most 2 (the text size in 1), one grip on the topic's bottom
right corner, 24px at 1440 and 390, Shift scales the text. The sweep is the
measurement; this pins the shape.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1] / "frontend"


def _html() -> str:
    return (ROOT / "index.html").read_text(encoding="utf-8")


def _css() -> str:
    return (ROOT / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def _body(file: str, name: str) -> str:
    text = frontend_text(file)
    start = text.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function ", text[start + 10 :])
    return text[start : start + 10 + (nxt.start() if nxt else len(text))]


def test_the_text_size_is_on_the_bar_not_behind_the_text_door():
    html = _html()
    size = html.index('id="wb-map-text-size"')
    door = html.index('id="wb-map-text-menu"')
    strip = html.index('id="wb-map-strip"')
    assert strip < size < door, "the size select sits on the bar, before the Text door"
    assert '<span class="wb-map-bar-size">' in html[strip:size]


def test_every_select_on_the_bar_is_drawn_as_a_row_of_presses():
    wire = _body("whiteboard-map.js", "wbWireMapChoices")
    assert 'querySelectorAll("#wb-map-strip select")' in wire
    assert "wbMapSizeStepper(select)" in wire and "wbMapPickRow(select)" in wire
    row = _body("whiteboard-map.js", "wbMapPickRow")
    # INBOX 665: previews, never a pill well, and the select stays the
    # control: a press sets it and fires its change, so no listener has to know.
    assert '"seg' not in row and '"wb-map-picks"' in row and 'setAttribute("role", "group")' in row
    assert 'select.dispatchEvent(new Event("change", { bubbles: true }))' in row
    assert "aria-pressed" in row and "wbMapPickGlyph(select.id, option.value)" in row
    # "Follow the map" is the trailing reset, not a peer.
    assert "wb-map-pick-follow" in row and "wbMapIsFollow" in row
    stepper = _body("whiteboard-map.js", "wbMapSizeStepper")
    assert '"stepper wb-map-size-stepper"' in stepper and "stepper-unit" in stepper
    assert 'select.dispatchEvent(new Event("change", { bubbles: true }))' in stepper
    assert "wbWireMapChoices();" in _body("whiteboard.js", "initWhiteboard")
    # Redrawn whenever the strip syncs to a new topic.
    assert "for (const draw of WB_MAP_CHOICE_REDRAWS) draw();" in _body("whiteboard-map.js", "wbSyncMapStrip")
    # The follow rows are marked where they are named.
    assert "blank.dataset.follow" in _body("whiteboard-map.js", "wbSyncMapStrip")
    assert "blank.dataset.follow" in _body("whiteboard-map.js", "wbSyncMapFill")
    css = _css()
    assert ".wb-map-choices" not in css
    picks = css[css.index(".wb-map-picks {"):]
    assert "flex-wrap: nowrap;" in picks[: picks.index("}")]


def test_one_resize_grip_on_the_corner_and_shift_scales_the_text():
    js = frontend_text("whiteboard-map.js")
    assert "wb-map-size-grip" not in js and "wbMapStartSizeDrag" not in js
    assert "wb-map-grips" not in _css()
    drag = _body("whiteboard-map.js", "wbMapStartResizeDrag")
    assert "moveEvent.shiftKey" in drag and "font_size: font" in drag
    css = _css()
    rule = css[css.index(".wb-map-resize-grip {") :]
    rule = rule[: rule.index("}")]
    assert "inset: auto -12px -12px auto" in rule
    # One size to the hand at every zoom: the sheet writes the inverse zoom
    # onto it (tests/test_wb_navigator_cost.py keeps the list whole).
    assert "scale(var(--wb-inv-zoom))" in rule


def test_a_door_never_opens_on_its_topic_and_has_one_selected_and_one_reset_look():
    """INBOX 814 (the owner: "when I change stuff in the tools for a mindmap
    node, I cant actually see what the difference is until I click off it").
    Measured on the base at 1440x560, 390x844 and 1440x420: the Shape door
    (336 by 210) covered the topic it edits, so a change that painted at once
    was covered at once. `scratchpad/ui-sweeps/mapfixmenu.js` is the
    measurement (rect intersection 0 at five viewports, the computed style
    changing before deselect); this pins the shape."""
    wb = frontend_text("whiteboard.js")
    assert "wbMapStripMenuOffTopic(menu, toggle)" in _body("whiteboard.js", "wbTrackMapStripMenu")
    assert 'menu.classList.contains("wb-map-strip-menu")) wbMapStripMenuOffTopic' in wb
    assert "function escapeMenuToBody(" in frontend_text("menus.js")
    css = _css()
    chosen = css[css.index(".wb-map-pick.is-inherited {") :]
    chosen = chosen[: chosen.index("}")]
    assert "background: var(--accent-surface)" in chosen and "inset" not in chosen
    assert ".wb-map-pick.is-inherited:not(.active)" not in css
    reset = css[css.index(".wb-map-pick-follow,\n#wb-map-reset {") :]
    assert "color: var(--muted)" in reset[: reset.index("}")]
    row = _body("whiteboard-map.js", "wbMapPickRow")
    assert "button.disabled = following" in row


def test_the_format_bar_follows_a_boards_edited_text_and_the_topic_buttons_step_aside():
    """INBOX 817: while a topic's text is edited the bar (bold to comment)
    stayed where it opened through a pan or zoom and could lie across the text,
    and the + / link buttons, fold toggle and grip overlapped the text box.
    `scratchpad/ui-sweeps/mapeditbar.js` measures the gap (8px, 0 intersection
    after a 200px pan and a zoom to 150%, at 1440 and 390)."""
    editor = frontend_text("editor.js")
    show = editor[editor.index("function selectionBarShow("):]
    show = show[: show.index("\n}\n")]
    assert "getSelection()" in show and "range.bottom + gap" in show
    work = _body("whiteboard.js", "wbZoomFrameWork")
    assert "selectionBarSync()" in work
    lazy = (ROOT / "css" / "library-lazy.css").read_text(encoding="utf-8")
    rule = lazy[lazy.index(".wb-map-node.wb-text-editing .wb-map-actions"):]
    rule = rule[: rule.index("}")]
    assert ".wb-map-collapse" in rule and ".wb-map-resize-grip" in rule and "display: none" in rule


def test_a_tree_lines_label_moves_with_the_line_on_every_frame_of_a_drag():
    """INBOX 818 (the owner: "labels on mind map links dont move with the
    links"). Measured by `scratchpad/ui-sweeps/maplabels.js`: during a 200px
    topic drag the label was 102px from its line's midpoint (the drag redrew
    the path, its twin and the handle, never the label; it caught up only at
    the drop), and at rest it stood 8.5px above the midpoint (`dy` -0.4em).
    After: 0px at rest, in the live frame, after the drop, a relayout, a pan
    and a zoom."""
    wm = frontend_text("whiteboard-map.js")
    update = wm[wm.index("function wbUpdateMapEdges("):]
    update = update[: update.index("\n}\n")]
    assert "_wbLabel" in update and "edge_label_dx" in update
    assert ".wb-map-edge-label" in wm[wm.index("function wbMapEdgeContext("):][:900]
    assert "text.dataset.child = path.dataset.child" in wm
    apply = wm[wm.index("function wbMapEdgeApply("):]
    apply = apply[: apply.index("\n}\n")]
    assert '"dominant-baseline", "central"' in apply and '"dy"' not in apply


def test_a_tools_kind_popover_is_lifted_clear_of_its_options_bar():
    """INBOX 823: the Line and Arrow choice (the Shapes popover) opened 6,232px2
    under the options bar (Size, Plain, Solid) beside it, z 20 under z 22.
    `scratchpad/ui-sweeps/toolpop.js` measures 0 at 1440 and 390; this pins it."""
    wb = frontend_text("whiteboard.js")
    assert "wbLiftMenuOffOptionsBar(menu);" in wb[wb.index("function wbOpenDockedMenu("):][:3200]
    lift = wb[wb.index("function wbLiftMenuOffOptionsBar("):]
    lift = lift[: lift.index("\n  }\n")]
    assert 'getElementById("wb-context")' in lift and "style.translate" in lift


def test_layers_says_what_a_tinted_row_means_and_nests_a_frames_items():
    """INBOX 824 (the owner asked whether the tint meant "in the frame"). The
    head counts the board's selection with a Clear, and a frame's items are
    nested under its row (measured by the mapfix sweep, since removed: head "2
    selected on the board", 3 nested rows indented 4 to 12.8px, folded to 0,
    Clear back to "Nothing selected", at 1440 and 390)."""
    html = _html()
    assert 'id="wb-layers-selected-count"' in html and 'id="wb-layers-clear"' in html
    lib = frontend_text("whiteboard-library.js")
    assert "wbLayersSelectedHead(selected.size)" in _body("whiteboard-library.js", "wbRenderLayers")
    rows = _body("whiteboard-library.js", "wbLayerRows")
    assert "wbFrameContents(frame.item, { withLocked: true })" in rows and "held: true" in rows
    assert "wbLayerFoldedFrames" in lib and 'aria-expanded' in lib


def test_a_frame_fits_its_contents_from_a_handle_a_corner_and_its_menu():
    """INBOX 821: double-click an edge handle fits that edge to what the frame
    holds plus 32 units, a corner two, the menu all four; an empty frame stays;
    one Undo step (`scratchpad/ui-sweeps/framefit.js`: gaps 32, undo back to
    the start, at 1440 and 390)."""
    wb = frontend_text("whiteboard.js")
    fit = _body("whiteboard.js", "wbFrameFit")
    assert "WB_FRAME_FIT_MARGIN = 32" in wb and "wbPushUndo({ action: \"move\"" in fit
    assert "holds nothing to fit" in fit and "prefers-reduced-motion" in fit and "150ms" in fit
    assert "wbFrameFit(" in wb[wb.index('const handle = e.target.closest?.(".wb-resize-handle, .wb-map-resize-grip");'):][:900]
    assert 'id: "fit-frame"' in frontend_text("whiteboard-commands.js")


def test_a_page_row_renames_in_place_and_has_a_kebab():
    """INBOX 822 (the owner: "I cant rename frames in the pages sidebar").
    Double-click (`detail === 2`, because the first press redraws the list and
    no `dblclick` follows), F2 or the row's kebab runs the canvas title's own
    editor on the row's name; `scratchpad/ui-sweeps/pagerename.js` measures
    Enter keeps, Escape cancels, one Undo step, the canvas title follows."""
    lib = frontend_text("whiteboard-library.js")
    rename = _body("whiteboard-library.js", "wbPageRename")
    assert "wbEditFrameTitle(nameEl, frame)" in rename
    menu = _body("whiteboard-library.js", "wbPageMenu")
    for words in ("Rename", "Fit to contents", "Present from here", "Delete the frame"):
        assert words in menu
    assert "e.detail === 2" in lib and 'e.key === "F2") wbPageRename(id)' in lib
    assert 'querySelector("[contenteditable]")' in lib


def test_a_selected_connector_has_a_visible_label_button():
    """INBOX 819 (part 1): a connector took a label only by Enter on the
    selected line and nothing on screen said so. The bar's Label button
    (`scratchpad/ui-sweeps/connlabel.js`: shown, opens the editor, the label
    draws and survives a reload at 1440 and 390). Its look (size, bold, colour,
    chip, position) and the double-click are open: see mapfix-1011.md."""
    html = _html()
    assert 'id="wb-prop-label"' in html and "ph-tag" in html
    wb = frontend_text("whiteboard.js")
    assert 'getElementById("wb-prop-label")?.addEventListener("click"' in wb
    assert 'labelButton.classList.toggle("hidden", !wbLinkTakesLabel(item, parsed))' in wb


# Map and board canvas: topic add buttons, raster refresh, outline editing, the Map tab and fit-to-view (INBOX 790 to 794).
_REPO = Path(__file__).resolve().parents[1]


def test_a_topics_add_buttons_are_surfaces_at_the_target_floor():
    """INBOX 791: the `+` and the library button on a node were transparent
    28px ghosts. A card surface, a hairline, `--target-min` (44 on touch), a
    body-size glyph, one size at every zoom, and a link glyph for the
    reference (a bookmarks glyph read as "copy")."""
    lazy = (_REPO / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    box = re.search(r"\.wb-map-actions > button:not\(#wb-map-actions-row\) \{([^}]*)\}", lazy)
    assert box
    for want in ("width: var(--target-min)", "height: var(--target-min)", "background: var(--modal-bg-opaque)", "border: 1px solid var(--ghost-btn-border)"):
        assert want in box.group(1), want
    # INBOX 816 scaled with the topic; the floor moved from 20 to 24px (and
    # touch holds 44) because a target under 24px fails WCAG 2.5.8 (audit 1028 U5).
    assert re.search(r"\.wb-map-actions \{\s*transform: scale\(clamp\(calc\(24 / 28 \* var\(--wb-inv-zoom\)\), 1, var\(--wb-inv-zoom\)\)\)", lazy)
    js = (_REPO / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    assert '"ph ph-link-simple"' in js and "bookmarks-simple" not in js
    wb = (_REPO / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert '".wb-map-actions"' in wb


def test_the_board_layers_are_rasterised_again_when_a_zoom_settles():
    wb = (_REPO / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    refresh = wb[wb.index("function wbRefreshRaster") :][:600]
    assert 'style.willChange = "auto"' in refresh and 'style.willChange = ""' in refresh
    publish = wb[wb.index("function wbPublishInvZoom") :][:200]
    assert "wbRefreshRaster()" in publish


def _slice(js: str, name: str, span: int = 2500) -> str:
    return js[js.index(f"function {name}") :][:span]


def test_outline_rows_read_until_asked_to_be_edited():
    """INBOX 792: "i dont think i should be typing in these outline options in
    the sidebar unless i like double click on them or press an edit button".
    A row is read-only; a double click, F2, Enter or its pencil opens it, Enter
    saves and Escape puts the old name back."""
    js = (_REPO / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    row = _slice(js, "wbOutlineRowEl", 2200)
    assert "field.readOnly = true;" in row and "wb-outline-edit" in row
    assert "readOnly = false" in _slice(js, "wbOutlineEdit")
    stop = _slice(js, "wbOutlineStopEdit")
    assert "cancel" in stop and "wbMapLabel(row._node)" in stop
    keys = js[js.index('getElementById("wb-outline-tree")?.addEventListener("keydown"') :][:2600]
    assert 'event.key === "F2"' in keys and 'event.key === "Escape"' in keys
    assert "wbOutlineStopEdit(row, { cancel: true })" in keys
    assert 'addEventListener("dblclick"' in js[js.index("wbOutlineEdit(row)") - 600 :][:1400] or "dblclick" in js
    mirror = js[js.index('getElementById("wb-outline-tree")?.addEventListener("input"') :][:300]
    assert "wbOutlineEditing(row)" in mirror
    css = (_REPO / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert "#wb-outline-tree .wb-outline-row.is-editing > .wb-outline-text" in css


def test_this_map_tab_is_tiles_actions_and_a_help_popover():
    """INBOX 791: "this side tab looks a little messy". The counts are
    number-over-label tiles two across (one builder with the stats dialog),
    the actions are one group of quiet buttons, and the Library hint is the
    help popover recipe."""
    js = (_REPO / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    lib = (_REPO / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")
    assert "wbMapStatsList(wbMapStats(wbMapIndex()), { tiles: true })" in lib
    assert "function wbMapStatsList(stats, { tiles = false } = {})" in js
    html = (_REPO / "frontend" / "index.html").read_text(encoding="utf-8")
    panel = html[html.index('data-side-panel="map"') :]
    panel = panel[: panel.index("</section>")]
    assert 'class="wb-side-actions"' in panel and 'data-help-for="wb-side-map-help"' in panel
    assert "wb-menu-item" not in panel, "the actions are buttons, not menu rows"
    for button in ("wb-side-map-look", "wb-side-map-expand", "wb-side-map-tidy"):
        assert f'class="ghost small" id="{button}"' in panel
    css = (_REPO / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.wb-map-stat-grid \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)", css)


def test_a_fit_goes_into_the_canvas_the_person_can_see():
    """INBOX 792: "the fitting to screen features ... should be based on what
    panels are currently showing and the screen resolution/size". The fit and
    the centring use the free area (the canvas box less the top bar, tools dock,
    sidebar and Format panel, each off the side it sits on), and a view still
    where the last fit put it is fitted again when a panel opens, closes or
    the window changes size; a pan or a zoom of the person's own ends that."""
    js = (_REPO / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert 'const WB_FIT_OCCLUDERS = ["#wb-topbar", "#wb-tools-panel", "#wb-sidebar", "#wb-format"];' in js
    fit = _slice(js, "wbZoomToFit", 1800)
    assert "wbFreeArea(container)" in fit and "container.getBoundingClientRect()" not in fit
    # Zoom to the selection (Shift+2) fits without refitting; every other fit refits.
    assert "refit = true }" in fit and "wbFit.on = refit" in fit
    center = _slice(js, "wbCenterOn", 900)
    assert "wbFreeArea(container)" in center
    zoom = _slice(js, "handleWbZoom", 400)
    assert "e.sourceEvent" in zoom and "wbFit.on = false" in zoom
    assert 'for (const id of ["whiteboard-container", "wb-sidebar", "wb-format", "wb-tools-panel"])' in js
    assert "setTimeout(wbRefitIfFitted, 200)" in js
