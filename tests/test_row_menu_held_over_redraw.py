"""A list redraw waits while a note row's menu is open.

The row's More actions menu lives in the row, so `renderEntries` rebuilding the
list took the menu out from under the pointer: a save landing a moment after
Make private closed the menu being read (deepflows private and link at 1440,
2 of 14 runs; the trace said "element was detached from the DOM").
"""

from tests._app_js import frontend_text


def _body(text: str, head: str) -> str:
    start = text.index(head)
    end = text.index("\n}", start)
    return text[start:end]


def test_render_entries_defers_while_a_row_menu_is_open():
    body = _body(frontend_text("js/notes-list.js"), "function renderEntries(appendOnly = false) {")
    guard = body.index('#entry-list > li [aria-haspopup="menu"][aria-expanded="true"]')
    assert "return renderEntries.afterMenu(heldMenu, appendOnly);" in body
    # Before the list is touched, so nothing of the open row is replaced.
    assert guard < body.index('const list = $("entry-list");')


def test_the_owed_draw_runs_once_when_the_menu_closes_or_its_row_goes():
    body = _body(frontend_text("js/notes-list.js"), "renderEntries.afterMenu = function (opener, appendOnly) {")
    assert "renderEntries.afterMenu.owed" in body  # one owed draw, however many were asked
    assert 'attributeFilter: ["aria-expanded"]' in body
    assert "opener.isConnected" in body
    assert "watch.disconnect();" in body
    assert "resolve(renderEntries(state.appendOnly));" in body
