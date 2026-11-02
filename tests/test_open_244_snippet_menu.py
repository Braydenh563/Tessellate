"""OPEN 244: right-click and long-press on a document's snippet row opened nothing.

The row menu (navigation.js `ROW_MENU_HOSTS`) finds a host by `closest` and then
the host's own ⋯ (`.menu-wrap > [aria-haspopup="menu"]`); the snippet item was
not a host, so neither gesture had a row to open.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text, with_pieces


def test_a_snippet_item_is_a_row_menu_host():
    text = app_js_text()
    block = text[text.index("const ROW_MENU_HOSTS") : text.index('].join(", ");', text.index("const ROW_MENU_HOSTS"))]
    assert '".doc-snippet-item"' in block


def test_the_snippet_item_holds_its_own_menu():
    kit = with_pieces("documents-codekit.js")
    build = kit[kit.index('li.className = "doc-snippet-item";') :][:1500]
    assert re.search(r"li\.appendChild\(kebabMenu\(", build)
