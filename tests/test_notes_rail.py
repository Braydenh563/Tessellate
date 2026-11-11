"""The note connections rail: when it is on screen, and what it is made of.

WORLD_CLASS_PLAN D2: "a note's page has a connections rail (backlinks, links,
related) that is always visible on desktop and a sheet on phone", and
`GET /resurface/near` had no place to be read beside a note. The rail is the
right-hand column of the Notes tab at 1280px and wider, for the note that is
open (being edited, expanded, jumped to) or selected (the list's focused row);
below 1280 it is not drawn and the card menu's Connections sheet is the way
in, as it was. Dismissing it is remembered.

The suite cannot lay the page out, so this holds the rule as text in the three
places it lives (the markup, the script, the stylesheet), which have to agree
on one number; `scratchpad/ui-sweeps/notesrail.js` measures it at 1440, 1280,
1024 and 390.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text
from tests._css_paths import CSS_DIR

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LIST_JS = (ROOT / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")
CONNECTIONS_JS = (ROOT / "frontend" / "js" / "connections.js").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css")))


def _rail_markup() -> str:
    notes = HTML.split('id="tab-notes"')[1].split('id="tab-chat"')[0]
    assert 'id="notes-rail"' in notes, "the rail is not in the Notes tab's markup"
    return notes.split('id="notes-rail"')[1].split("</aside>")[0]


def test_the_rail_is_a_column_of_the_notes_layout_after_the_list():
    notes = HTML.split('id="tab-notes"')[1].split('id="tab-chat"')[0]
    after_main = notes.split("</div><!-- .tab-main -->")[1]
    assert re.search(r'<aside[^>]*id="notes-rail"', after_main), (
        "the rail is the Notes layout's third column, after .tab-main, so it sits "
        "beside the list rather than inside the scroller the list lives in"
    )
    assert re.search(r'<aside[^>]*id="notes-rail"[^>]*\bhidden\b', after_main), (
        "the rail starts hidden: it arrives with the note it is about"
    )


def test_the_rail_head_is_the_panel_head_recipe():
    rail = _rail_markup()
    assert re.search(r'<h3 class="panel-head[^"]*"', rail), "the head is `h3.panel-head` (DESIGN.md)"
    assert rail.count('class="chip') <= 1, "a panel head carries at most one chip"
    assert 'data-help-for="notes-rail-help"' in rail and 'id="notes-rail-help"' in rail
    close = re.search(r'<button[^>]*id="notes-rail-close"[^>]*>', rail)
    assert close and "aria-label=" in close.group(0) and "title=" in close.group(0)


def test_the_presence_rule_is_one_number_in_script_and_stylesheet():
    match = re.search(r"const NOTES_RAIL_MIN_WIDTH = (\d+);", LIST_JS)
    assert match, "notes-list.js names the width the rail appears at"
    width = int(match.group(1))
    assert width == 1280
    assert "matchMedia(`(min-width: ${NOTES_RAIL_MIN_WIDTH}px)`)" in LIST_JS, "the script asks the window, not a guess"
    assert re.search(rf"@media \(max-width: {width - 1}\.98px\)\s*\{{[^}}]*#notes-rail", CSS), (
        "the stylesheet takes the rail away below the same width, so a frame "
        "drawn before the script runs cannot show it"
    )


def test_the_rail_reads_the_two_routes_and_remembers_being_dismissed():
    #: The answer is drawn by connections.js (`drawNotesRail`, moved for the boot gzip cap, INBOX 1525).
    rail = LIST_JS + CONNECTIONS_JS
    assert "/connections`" in rail and "/resurface/near/" in rail
    assert 'NOTES_RAIL_KEY = "notes-rail"' in LIST_JS
    assert "prefs.set(NOTES_RAIL_KEY" in LIST_JS


def test_the_sheet_and_the_rail_draw_rows_with_one_builder():
    app = app_js_text()
    assert "function buildConnectionGroups(" in app
    sheet = app.split("async function openConnections(")[1].split("\n}\n")[0]
    assert "buildConnectionGroups(" in sheet, "the sheet draws its groups with the shared builder"
    assert "buildConnectionGroups(" in CONNECTIONS_JS.split("async function drawNotesRail(")[1], "and so does the rail"


def test_the_rail_gives_way_before_the_list_drops_under_600():
    """D2's gate is a reading column of at least 600px. The rail's width is
    set against the default sidebar, and a sidebar dragged to its widest left
    the list at 573px at 1280 (`notesrail.js` with SIDEBAR=wide), so the rail
    measures the list and gives way to the sheet when it would be narrower,
    and re-decides when the sidebar is resized."""
    assert "const NOTES_RAIL_MIN_READING = 600;" in LIST_JS
    body = LIST_JS.split("async function renderNotesRail(")[1].split("\n}\n")[0]
    assert "NOTES_RAIL_MIN_READING" in body and "getBoundingClientRect().width" in body
    assert "new ResizeObserver(" in LIST_JS and '.observe($("sidebar"))' in LIST_JS


def test_opening_a_cards_menu_does_not_open_the_rail_under_it():
    """The review of 2026-09-27 (`scratchpad/ui-sweeps/anchorsmotion.js`): a
    card's ⋯ is a button inside its row, so pressing it is a `focusin` on the
    row, and the rail opened 120ms later. The column takes 318px from the
    list and the list's dock wraps to a second line, so the row moved 318px
    left and 44px down under a menu already placed beside where its ⋯ had
    been: at 1440x600, 118px between the menu and its opener, the menu over
    the rail. A menu is acting on a note, not choosing one to read: only focus
    on the row itself, or a control that is not a menu's, selects it."""
    wire = LIST_JS[LIST_JS.index('const rail = $("notes-rail");') :]
    focus = wire[wire.index('list.addEventListener("focusin"') :]
    focus = focus[: focus.index("\n  });\n")]
    assert ".menu-wrap" in focus and ".action-menu" in focus, "a card's menu opening still selects the note for the rail"
