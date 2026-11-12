"""No interactive control inside another one (INBOX 433, WCAG 2.2 4.1.2).

axe-core's `nested-interactive` rule, measured with
`scratchpad/ui-sweeps/axe.js`: every Library card was an `<article
role="button">` holding its own tick and its own ⋯ (35 nodes across the
two themes), and six Settings fold heads were `<summary>`s holding their '?'.
A screen reader announces the outer control and cannot reach the inner ones
as themselves, and the platform's own keyboard rules for a button do not
expect anything focusable inside it.

The fix is the accessible card (DESIGN.md, the recipe index): the card is
not a control. Its title is the one control that opens it (`cardOpener`,
menus.js), and that title's click area is stretched over the card by a
`::after` overlay, so a click anywhere on the card still opens it while the
tick and the ⋯ sit above the overlay as controls of their own.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
LIBRARY = (FRONTEND / "js" / "library.js").read_text(encoding="utf-8")
WHITEBOARD = (FRONTEND / "js" / "boards-gallery.js").read_text(encoding="utf-8")
MENUS = (FRONTEND / "js" / "menus.js").read_text(encoding="utf-8")
NAVIGATION = (FRONTEND / "js" / "navigation.js").read_text(encoding="utf-8")
CSS = "\n".join(
    re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.S)
    for p in sorted((FRONTEND / "css").glob("*.css"))
)


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for index in range(source.index(") {", start) + 2, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(name)


def test_the_opener_is_one_shared_builder():
    opener = _function(MENUS, "cardOpener")
    assert 'setAttribute("role", "button")' in opener
    assert "tabIndex" in opener
    assert '"Enter"' in opener and '" "' in opener
    # A link the title's markdown drew would be a control inside the
    # control again; the title is a name, so its links are unwrapped.
    assert "a[href]" in opener
    assert 'classList.add("card-open")' in opener


def test_the_library_card_is_not_itself_a_control():
    card = _function(LIBRARY, "libraryCard")
    assert 'card.setAttribute("role", "button")' not in card
    assert "card.tabIndex" not in card
    assert "cardOpener(title" in card
    # Its controls still take their own presses: the overlay sits under them.
    assert "card.addEventListener(\"keydown\"" not in card


def test_the_board_card_and_the_document_row_use_the_same_opener():
    gallery = _function(WHITEBOARD, "drawLibraryBoardsGallery")
    assert 'card.setAttribute("role", "button")' not in gallery
    assert "card.tabIndex" not in gallery
    assert "cardOpener(title" in gallery
    docs = LIBRARY[LIBRARY.index('open.className = "doc-list-item";') :][:4000]
    assert 'open.setAttribute("role", "button")' not in docs
    assert "open.tabIndex" not in docs
    assert "cardOpener(title" in docs


def test_the_one_tab_stop_moves_to_the_opener():
    stop = _function(LIBRARY, "setLibraryCardStop")
    assert "card.tabIndex" not in stop
    assert 'const LIBRARY_CARD_STOPS = ".card-open, .library-card-tick, .library-card-menu > button";' in LIBRARY
    ensure = _function(LIBRARY, "ensureLibraryGridStop")
    assert ".card-open[tabindex='0']" in ensure
    # The arrow keys move between the openers, the one stop of each card.
    assert '["#library-grid", ".library-card .card-open"]' in NAVIGATION
    assert '["#library-boards-grid", ".library-card .card-open"]' in NAVIGATION
    assert '["#library-docs-list", ".doc-list-item .card-open"]' in NAVIGATION


def test_the_overlay_covers_the_card_and_the_controls_sit_above_it():
    after = re.search(r"\.card-open::after\s*\{([^}]*)\}", CSS)
    assert after, "no stretched overlay for .card-open"
    assert "position: absolute" in after.group(1)
    assert "inset: 0" in after.group(1)
    # The hosts are the overlay's containing block.
    for host in (".library-card", ".doc-list-item"):
        assert re.search(re.escape(host) + r"\s*\{[^}]*position:\s*relative", CSS), host
    # Above it: the ticks, the menus and any link in a preview.
    assert "z-index: 1" in after.group(1)
    # The lift is its own rule and may sit before the overlay (UI plan 13b
    # moved each beside its component): z-index on other elements, no tie.
    controls = (".library-card-tick", ".doc-list-tick", ".menu-wrap", ".library-card-preview a")
    lifts = [m.group(1) for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]*)\{\s*z-index:\s*2;\s*\}", CSS)]
    lifted = [sel for sel in lifts if ".library-card-tick" in sel]
    assert lifted, "nothing is lifted above the overlay"
    for control in controls:
        assert control in lifted[0], control
    # The card still shows where the keyboard is: the ring the card had.
    assert ":has(.card-open:focus-visible)" in CSS


# --- a fold head's '?' is beside its <summary>, not in it -------------------
#
# Six Settings fold heads (and three more axe could not see, inside closed
# folds) were `<summary>`s holding their '?'. The '?' is the first child of
# a `.fold-help-wrap` now, the summary keeps an empty `.fold-help-slot` where
# it was, and `placeFoldHelp` (settings.js) draws the button over the slot.
# `scratchpad/ui-sweeps/foldhelp.js` measured all nine at 1440 and 390:
# identical to the tenth of a pixel to the old positions.

INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
SETTINGS = (FRONTEND / "js" / "settings.js").read_text(encoding="utf-8")

# A summary that carries its one action (DESIGN.md's fold recipe allowed it)
# is still a control inside a control; this is the one left, a ratchet that
# may only shrink.
SUMMARY_CONTROLS_ALLOWED: set[str] = set()


def _summaries() -> list[str]:
    return re.findall(r"<summary\b[^>]*>(.*?)</summary>", INDEX, re.S)


def test_no_summary_in_the_markup_holds_a_help_button():
    offenders = [body for body in _summaries() if "data-help-for" in body]
    assert not offenders, offenders[0][:200]


def test_no_summary_holds_any_other_control_but_the_ratchet():
    found = set()
    for body in _summaries():
        for tag in re.finditer(r"<(?:button|input|select|textarea|a\s[^>]*href)\b[^>]*>|tabindex=", body):
            ident = re.search(r'id="([^"]+)"', tag.group(0))
            found.add(ident.group(1) if ident else tag.group(0)[:60])
    assert found <= SUMMARY_CONTROLS_ALLOWED, found - SUMMARY_CONTROLS_ALLOWED


def test_each_fold_help_sits_beside_its_fold_over_a_slot():
    wraps = re.findall(
        r'<div class="fold-help-wrap">\s*<button\b([^>]*)>.*?</button>\s*<details\b[^>]*>\s*<summary>(.*?)</summary>',
        INDEX,
        re.S,
    )
    # Twelve: Effects & accessibility gained the motion help (2026-10-05); Embedding models left the fold list when it moved into Search and index (INBOX 700); Import a document, Import from another app and Web clipper became folds (audit S68, 2026-11-02).
    assert len(wraps) == 12, len(wraps)
    for attrs, summary in wraps:
        assert "fold-help" in attrs and "data-help-for=" in attrs, attrs
        assert '<span class="fold-help-slot" aria-hidden="true"></span>' in summary


def test_the_button_is_placed_over_its_slot_and_still_opens_its_fold():
    place = _function(SETTINGS, "placeFoldHelp")
    assert ".fold-help-slot" in place and "getBoundingClientRect" in place
    assert "ResizeObserver" in _function(SETTINGS, "wireFoldHelps")
    assert 'onSurface("settings", wireFoldHelps);' in SETTINGS
    folds = _function(SETTINGS, "wireSettingsFolds")
    assert ":scope.fold-help-wrap > .fold-help" in folds
    assert re.search(r"\.fold-help-wrap\s*\{[^}]*position:\s*relative", CSS)
    assert re.search(r"\.fold-help-wrap > \.fold-help\s*\{[^}]*position:\s*absolute", CSS)
    slot = re.search(r"\.fold-help-slot\s*\{([^}]*)\}", CSS)
    assert slot and "visibility: hidden" in slot.group(1) and "var(--target-min)" in slot.group(1)


def test_the_placement_is_divided_by_the_dialogs_entrance_scale():
    # INBOX 1514: Settings rises from `scale: 0.985`, the observer fires on
    # that first frame, and bounding rects are drawn size, so every '?' in
    # Settings sat 4.8px (1440) short of its slot for good: a scale changes
    # no layout size, so nothing re-placed it. The wrapper's computed width is
    # its layout width; the ratio is the scale to divide out.
    place = _function(SETTINGS, "placeFoldHelp")
    assert "getComputedStyle(wrap).width" in place
    assert re.search(r"at\.left - box\.left\) / scale", place)
    assert re.search(r"at\.top - box\.top\) / scale", place)
    assert re.search(r"@starting-style\s*\{[^}]*scale:\s*0\.985", re.sub(r"\s+", " ", CSS))


# --- the Manage categories panel is a grid, not a listbox of buttons ---------
#
# Each row was `role="option"` holding its ⋯ (`tabindex="-1"` does not take a
# control out of reach of a screen reader, so axe still counted 7). An option
# may hold nothing interactive; a grid's cell may. The rows are `role="row"`
# with `aria-selected` in a multiselectable `role="grid"`; the first cell
# (dot, name, count) is the roving stop and the ⋯ is the last cell.

CATEGORIES = _js_scope.unwrapped((FRONTEND / "js" / "categories-panel.js").read_text(encoding="utf-8"))


def test_the_category_rows_are_grid_rows_with_the_menu_in_its_own_cell():
    panel = _function(CATEGORIES, "openManageCategories")
    assert 'list.setAttribute("role", "grid")' in panel
    assert 'list.setAttribute("aria-multiselectable", "true")' in panel
    assert '"listbox"' not in CATEGORIES and '"option"' not in CATEGORIES
    rows = _function(CATEGORIES, "drawManageCategoryRows")
    assert 'li.setAttribute("role", "row")' in rows
    assert 'li.setAttribute("aria-selected"' in rows
    assert "li.tabIndex" not in rows
    assert 'main.setAttribute("role", "gridcell")' in rows
    assert "main.tabIndex" in rows
    assert 'menu.setAttribute("role", "gridcell")' in rows


def test_the_category_keys_act_from_the_row_stop():
    keys = _function(CATEGORIES, "wireManageCategoryKeys")
    for key in ('"ArrowDown"', '"ArrowUp"', '"Home"', '"End"', '" "', '"Enter"', '"F2"', '"Delete"', '"ContextMenu"', '"F10"'):
        assert key in keys, key
    assert ".manage-cat-main" in keys
    # The row shows the keyboard's place: the ring the focused row had.
    assert ".manage-cat-row:has(> .manage-cat-main:focus-visible)" in CSS
