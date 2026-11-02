"""DX6 and DX26 (audit 1102): one insert catalogue, a formatting toolbar of one row.

Insert is a button that opens the "/" menu, so the toolbar can never list a
block the slash menu lacks or list one twice. The one-row measure (1440:
82.8 px, 26 controls, two rows before; 46.8 px, 19 controls after) is a
browser number; these pin the source that makes it so.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
EDITOR = (JS / "editor.js").read_text(encoding="utf-8")
ROWS = EDITOR[EDITOR.index("function editorBlockRows") : EDITOR.index("function editorBackOverTrail")]
BAR = INDEX[INDEX.index('id="doc-toolbar" role="toolbar"') : INDEX.index('id="doc-phone-bar"')]

#: What was slash-only in the audit; each must be a catalogue row, and the
#: toolbar reaches the catalogue through the one Insert button.
SLASH_ONLY = [
    "image", "callout-note", "flowchart", "math", "footnote", "toc", "columns", "page-break",
    "h4", "h5", "h6", "quote", "codeblock", "table", "divider", "wikilink", "file-link",
]


def test_every_slash_only_block_is_a_catalogue_row_and_insert_opens_it():
    for row in SLASH_ONLY:
        assert f'id: "{row}"' in ROWS or f"id: `{row.split('-')[0]}-${{kind}}`" in ROWS, row
    assert len(re.findall(r'data-md="insert"', BAR)) == 1


def test_no_catalogue_row_is_listed_twice():
    ids = re.findall(r'add\(\{ id: "([a-z0-9-]+)"', ROWS)
    assert len(ids) > 40 and len(ids) == len(set(ids))
    labels = re.findall(r'add\(\{ id: "[a-z0-9-]+", group: "[A-Za-z]+", icon: "[^"]+", label: "([^"]+)"', ROWS)
    assert len(labels) == len(set(labels))


def test_the_toolbar_has_no_second_catalogue():
    menus = DOCS[DOCS.index("const EDITOR_TOOLBAR_MENUS") : DOCS.index("const EDITOR_TOOLBAR_BUTTONS")]
    for gone in ('id: "headings"', 'id: "blocks"', 'id: "insert"'):
        assert gone not in menus
    assert "<details" not in BAR[BAR.index('id="doc-toolbar-insert"') - 50 : BAR.index('id="doc-toolbar-insert"') + 400]
    for kind in ("h1", "h2", "h3", "quote", "codeblock", "table", "hr", "wikilink", "footnote", "image"):
        assert f'data-md="{kind}"' not in BAR, f"{kind} is an Insert row, not a toolbar control"


def test_numbered_list_is_on_the_bar_once():
    assert BAR.count('data-md="ol"') == 1


def test_the_second_row_menu_is_worded_and_the_mount_gives_notes_an_insert():
    assert "setLabel(summary, `${menu.icon} ${menu.label}`)" in DOCS
    assert "if (!bar.querySelector('[data-md=\"insert\"]'))" in DOCS


def test_slash_file_no_longer_falls_through_to_a_callout():
    assert 'id: "file-link"' in ROWS and '"attachment"' in ROWS
