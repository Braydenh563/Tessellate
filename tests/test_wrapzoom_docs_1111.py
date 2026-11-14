"""The Documents, code, diagram and whiteboard surfaces at every zoom (2026-11-11).

The owner: "make sure the wrapping and ui issues arent an issue anywhere else
from zoom or resolution". Measured by scratchpad/ui-sweeps/wrapzoom-docs.js
across 1280x720 to 2560x1440 at 100 to 200 %, and 768x1024. Each test pins
one defect class's fix where a static read can see it; the sweep is the
measurement.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def _at_blocks(css: str, prelude: str) -> list[str]:
    """The bodies of every at-rule whose prelude is exactly `prelude`."""
    out = []
    start = 0
    while True:
        i = css.find(prelude, start)
        if i < 0:
            return out
        j = css.index("{", i)
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append(css[j + 1 : k - 1])
        start = k


def _rule(block: str, selector_part: str) -> str:
    for sel, body in re.findall(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", block):
        if selector_part in sel:
            return body
    return ""


# ---- a header row whose items wrap onto a second line -----------------------


def test_a_code_documents_dock_folds_its_words_before_it_wraps():
    """A code file's actions were 808px (1062 with the Python line) in a 931px
    dock at 1280, so the name took a line and the actions broke in two. Below
    Phase 9's 1100 of dock (test_breakpoints: no width of its own) Back is its
    arrow, Snippets its icon, a code file's Format and Assistant theirs, and the
    Python line is cut with an ellipsis; while that line is in the row its
    lesser buttons are icons at any width (the 1100 to 1165 band); under 820 it
    leaves the row for the card's notice."""
    css = _css("library-lazy.css")
    wide = "".join(_at_blocks(css, "@container docdock (max-width: 1099.98px)"))
    assert ".doc-back-label" in wide and "#doc-code-snippets-open > .doc-ai-label" in wide
    assert "#tab-documents.doc-is-code .doc-ai-label" in wide
    assert "#doc-code-format > .toolbar-word" in wide
    why = _rule(wide, "#doc-code-run-why")
    assert "text-overflow: ellipsis" in why and "white-space: nowrap" in why and "max-width" in why
    assert "flex-basis: 8rem" in _rule(wide, ".doc-dock > .doc-dock-identity")
    assert "min-width: 5rem" in _rule(wide, ".doc-dock-identity > .doc-title-input")
    #: A class the dock wears while the Python line shows (docRunSyncAvailability),
    #: not a `:has()`: test_has_invalidation caps those.
    state = "#tab-documents.doc-is-code .doc-dock.doc-run-why"
    assert "display: none" in _rule(css, state + " :is(.doc-ai-label, #doc-code-format > .toolbar-word)")
    assert "flex-basis: 8rem" in _rule(css, state + " > .doc-dock-identity")
    narrow = "".join(_at_blocks(css, "@container docdock (max-width: 819.98px)"))
    assert "display: none" in _rule(narrow, "#doc-code-run-why")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # The cut line's tooltip says it whole.
    assert 'title="Install Python in Settings, Packages, to run Python files">Install Python in Settings, Packages</button>' in html


def test_the_dock_is_one_row_at_a_tablet_and_the_drafts_actions_at_a_phone():
    """768x1024: the dock is 652px, the 44px targets make the actions 539 and
    the name asked for 128 beside them, so it took a line (94px). Below 820 of
    dock the save state leaves the row (it did only below 600), which is 603
    and one 44px line for markdown and .py. The writing room's draft actions
    were 294px in a 286px column at 360 (96px): a 4px gap and the save word's
    8px sides make them one 44px row. Phase 9's breakpoints only."""
    css = _css("library-lazy.css")
    mid = "".join(_at_blocks(css, "@container docdock (max-width: 819.98px)"))
    assert "display: none" in _rule(mid, ".doc-dock-status")
    phone = "".join(_at_blocks(css, "@container docdock (max-width: 599.98px)"))
    assert ".doc-dock-status" not in phone
    chat = _css("04-chat-dock-appearance.css")
    small = "".join(_at_blocks(chat, "@media (max-width: 599.98px)"))
    assert re.search(r"\.draft-actions-row \{\s*column-gap: var\(--space-1\)", small)
    assert "padding-inline: var(--space-3)" in _rule(small, "#draft-save")


# ---- a split button breaking apart ---------------------------------------------


def test_the_side_panes_no_model_line_places_the_split_button_under_the_words():
    """offline-split.js swaps the notice's `.ghost` action for
    `.split-button.ai-offline-split`; the grid that put the action under the
    words matched only `.ghost`, so the split took column 1 and the words
    stood in 42px, one per line."""
    css = _css("library-lazy.css")
    body = _rule(css, "#doc-assist-model-line > :is(.ghost, .ai-offline-split)")
    assert "grid-column: 2" in body and "margin-inline-start: 0" in body
    js = (ROOT / "frontend" / "js" / "offline-split.js").read_text(encoding="utf-8")
    assert 'split.className = "split-button ai-offline-split"' in js


# ---- a narrow pane in a wide window -----------------------------------------------


def test_the_diagram_dock_answers_to_its_pane_not_the_window():
    """Split view at 1280 gave the builder 428px; the one-row dock's word
    drop and scroll fallback keyed on the window (under 600), so the menu sat
    22px past the pane. The pane (`.dgm`, an inline-size container) decides,
    and the scroller does not shrink in the pane's column."""
    css = _css("diagram-lazy.css")
    narrow = "".join(_at_blocks(css, "@container (max-width: 599.98px)"))
    assert "display: none" in _rule(narrow, ".dgm-kindword")
    dock = _rule(narrow, ".dgm-dock:has(> .dgm-addsplit)")
    assert "overflow-x: auto" in dock and "flex-shrink: 0" in dock


# ---- a hover bar over the content it acts on --------------------------------------


def test_the_rendered_tables_bar_has_its_own_strip_under_the_table():
    """The bar sat half over the table's bottom edge (translateY(50%)) and
    covered the last row's last cell. It now sits in a strip the block keeps
    below the table on a screen that hovers."""
    css = _css("09-editor.css")
    bar = _rule(css, "#doc-preview .md-table-block > .code-bar")
    assert "translateY" not in bar and "inset-block-end: 0" in bar
    hover = "".join(_at_blocks(css, "@media (hover: hover)"))
    assert "padding-block-end: 2.5rem" in _rule(hover, "#doc-preview .md-table-block")


# ---- a shelf row and the panel above it --------------------------------------------


def test_the_shelfs_picker_section_shortens_before_the_shelf_wraps():
    """A map's Layout section (two selects and Tidy, 370px) sent Edit to a
    second row at 1280. In the bottom shelf it asks for 12rem, grows back to
    its own width, and its pickers ellipsise."""
    css = _css("06-timeline-dialogs.css")
    sec = _rule(css, '.whiteboard-floating-panel:not([data-dock="side"]) .wb-tool-section:has(.select-shell)')
    assert "flex: 1 1 12rem" in sec and "max-width: max-content" in sec and "min-width: 0" in sec
    row = _rule(css, '.wb-tool-section:has(.select-shell) > .wb-tool-section-row')
    assert "flex-wrap: nowrap" in row
    assert "min-width: 4.5rem" in _rule(css, ".wb-tool-section-row > .select-shell")
    ellipsis = _rule(_css("07-whiteboard-misc.css"), ".select-value")
    assert "text-overflow: ellipsis" in ellipsis


def test_a_whiteboard_side_section_scrolls_inside_its_panel():
    """The map tab's facts and actions were 263px in a 197px section at
    960x540@2: they ran out of the panel over the shelf."""
    body = _rule(_css("07-whiteboard-misc.css"), ".wb-side-section")
    assert "overflow-y: auto" in body and "min-height: 0" in body


# ---- a menu cut by the view it opens in ----------------------------------------------


def test_a_nested_submenu_takes_its_menus_width_not_its_own():
    """Below 820 a submenu is a nested level of the same menu; a whiteboard
    submenu kept `.wb-board-menu`'s 19rem inside the menu's padded 19rem box
    and every row was cut 8px at the right."""
    css = _css("02-chat-graph.css")
    nested = "".join(_at_blocks(css, "@media (max-width: 819.98px), (hover: none)"))
    body = _rule(nested, ".action-menu.submenu")
    assert "position: static" in body and "width: auto" in body


def test_a_menu_left_in_place_is_capped_to_what_clips_it():
    """The board menu fitted the whiteboard view when it opened; a nested
    level made it taller and it ran past the view's clipping edge."""
    js = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    body = js[js.index("function escapeAndCapMenu") :]
    body = body[: body.index("\n}\n")]
    assert "menu._escapedHome ? null : menuClippingAncestor(menu)" in body
    assert "Math.min(window.innerHeight, clipper.getBoundingClientRect().bottom)" in body
    assert "floor - top - margin" in body


# ---- a side panel that covers the controls beside or under it ---------------


def test_the_format_panel_leaves_the_selection_bar_and_the_zoom_cluster_clear():
    """At 768 the Format panel reached down over the zoom cluster on the shelf
    and the selection bar's Duplicate and Delete stood under it: the bar gets
    the board less the panel, its fold reruns when the panel opens or shuts,
    and under 820 the panel's foot clears the cluster."""
    css = _css("library-lazy.css")
    wide = "".join(_at_blocks(css, "@media (min-width: 600px)"))
    assert "calc(100% - 18.5rem - 5rem)" in _rule(wide, "#wb-format:not(.hidden)) > #wb-context")
    mid = "".join(_at_blocks(css, "@media (min-width: 600px) and (max-width: 819.98px)"))
    assert "var(--target-min) + 2 * var(--space-1)" in _rule(mid, ".wb-format")
    js = frontend_text("whiteboard.js")
    sig = next(line for line in js.splitlines() if "const foldSig =" in line)
    assert "fmtOpen" in sig

def test_the_arrange_rows_put_four_touch_targets_under_their_name():
    """Four 44px targets are wider than the field track beside a 6rem name;
    under the finger the name takes its own line and the buttons stay one row."""
    css = _css("library-lazy.css")
    touch = "".join(_at_blocks(css, "@media (max-width: 819.98px), (pointer: coarse)"))
    assert "minmax(0, 1fr)" in _rule(touch, ".wb-fmt-commands > .wb-fmt-row")
    assert "flex-wrap: nowrap" in _rule(css, ".wb-fmt-commands .wb-fmt-buttons")
