"""Audit 1031 class 31 (BD5, BD9, BD10, BD11, BD12): the board says what it does.

BD5: a locked item is `aria-disabled` as well as pinned. BD9: Tab names the item
and its place (not "selected" again) and the board's `aria-activedescendant` is
that item. BD10: the long context menu is flyout groups, not seventeen flat
rows. BD11: Board, Show hints brings the dismissed card back. BD12: a PNG export
adds to the image library only when the dialog says so."""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = frontend_text("whiteboard.js")
CMDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    return source.split(head, 1)[1].split("\n}\n", 1)[0]


def test_a_locked_item_is_aria_disabled_and_unlocking_clears_it():
    body = _body(JS, "function wbPaintLocks()")
    assert 'el.setAttribute("aria-disabled", "true");' in body
    assert 'el.removeAttribute("aria-disabled");' in body


def test_the_tab_walk_says_name_and_place_and_sets_the_active_descendant():
    body = _body(JS, "function wbWalkItems(dir)")
    assert "${next + 1} of ${items.length}`" in body and ", selected`" not in body
    assert 'container.setAttribute("aria-activedescendant", el.id);' in body
    assert 'removeAttribute("aria-activedescendant")' in _body(JS, "function clearWbSelection()")


def test_the_board_context_menu_groups_its_rows_into_flyouts():
    body = _body(JS, "function wbBuildContextMenu(kind)")
    assert 'if (rows.length > 1 && typeof buildMenuGroupButton === "function")' in body
    assert 'subItem("Export", (sub) => {' in body
    assert 'item("Export selection…"' not in body
    for label in ('Library: "ph:books Save to the library"', 'Arrange: "ph:align-left Arrange"'):
        assert label in body


def test_show_hints_is_a_board_menu_row_with_a_palette_row_and_clears_the_dismissal():
    assert 'id="wb-show-hints" data-wb-closes data-wb-surface="board"' in HTML
    assert 'id: "show-hints"' in CMDS and 'run: wbClickId("wb-show-hints")' in CMDS
    handler = JS.split('$("wb-show-hints")?.addEventListener("click", () => {', 1)[1].split("});", 1)[0]
    assert 'prefs.remove("wbEmptyHintDismissed");' in handler and "wbHintForcedOpen = true;" in handler


def test_a_png_export_adds_to_the_library_only_when_asked():
    assert "library: saved.library === true," in JS
    body = _body(JS, "async function wbExportPng(scope)")
    assert "if (!library) {" in body and body.index("if (!library)") < body.index("uploadToLibrary")
    assert 'libraryBox.id = "wb-export-library";' in JS
    assert 'libraryRow.hidden = format.value !== "png";' in JS
