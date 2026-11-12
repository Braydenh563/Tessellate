"""Audit 1031 class 28: keyboard and target size (UX1, UX2, SH11, N21, N37, BD6, BD8).

Measured on the running app (scratchpad sweeps, 1440 and 390): the Tab count from
the top of the page to the first note went from 100+ (35 categories, each a name
and a menu) to 32 with one stop for the category list and 2 with the skip link;
"Show more", the rail's link menus, suggested-tag controls and Library titles
reach 24 px; board grips take a 24 px box on a coarse pointer."""

from __future__ import annotations

import re
from pathlib import Path
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = sheets(*FORMER_08)
FLOOR = CSS[CSS.index("The target floor (audit 1031 class 28") :]


def _rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", FLOOR)
    assert match, selector
    return match.group(1)


def test_the_category_list_is_one_tab_stop_with_arrows_home_end_and_the_menu_on_the_right_arrow():
    text = (JS / "notes-list.js").read_text(encoding="utf-8")
    assert "sidebarRovingRows(ul);" in text
    roving = text.split("function sidebarRovingRows", 1)[1].split("\n}\n", 1)[0]
    assert "li.tabIndex = li === stop ? 0 : -1" in roving and "button.tabIndex = -1" in roving
    keys = text.split("function wireSidebarRowKeys", 1)[1].split("// --- Manage categories", 1)[0]
    for key in ("ArrowDown", "Home", "End", "ArrowRight", "ArrowLeft"):
        assert f'"{key}"' in keys, key


def test_a_skip_link_jumps_past_the_chrome_to_the_list():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="skip-to-list" class="skip-link">Skip to the list<' in html
    assert html.index('id="skip-link"') < html.index('id="skip-to-list"') < html.index('id="top-bar"')
    assert '$("skip-to-list").addEventListener("click"' in (JS / "phone-shell.js").read_text(encoding="utf-8")


def test_show_more_the_rail_menus_and_the_board_grips_meet_the_floor():
    assert "min-height: var(--target-min)" in _rule("#entry-list .entry-more,\n#entry-list:not(.is-rows) > li:not(.list-window-sentinel) > .entry-more")
    assert "min-block-size: var(--target-min)" in re.search(r"\n\.card-open \{([^}]*)\}", CSS).group(1)
    # The coarse block that holds the board grips, found by its selector rather than
    # by being the file's last coarse block (L-general-52 appended another after it).
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    grips = next(b for b in lazy.split("@media (pointer: coarse)")[1:] if b.lstrip(" {\n").startswith(".wb-resize-handle"))
    assert "border: var(--space-3) solid transparent" in grips.split("\n}\n")[0]
    # Where they are declared: the rail's link menus and a card's task boxes.
    assert re.search(r"@media \(pointer: fine\) \{\s*#entry-list \.link-connection > \.menu-wrap \{[^}]*\}\s*#entry-list \.link-connection > \.menu-wrap > button \{\s*width: 1\.5rem;\s*height: 1\.5rem;", CSS)
    forms = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert re.search(r'entry-task > input\[type="checkbox"\]:disabled \{\s*width: 1\.125rem;\s*height: 1\.125rem;', forms)


def test_a_suggested_tags_controls_are_buttons_not_spans_with_a_role():
    text = ((JS / "note-cards.js").read_text(encoding="utf-8") + (JS / "entry-card.js").read_text(encoding="utf-8"))
    block = text.split("const suggestions = options.actions", 1)[1].split("meta.appendChild(group)", 1)[0]
    assert 'const take = document.createElement("button")' in block
    assert 'const discard = document.createElement("button")' in block
    assert "makeUnlinkAccessible" not in block
    assert "align-self: stretch" in CSS.split(".suggested-tag > button", 1)[1].split("}", 1)[0]


def test_a_library_or_board_card_is_named_by_its_visible_words_first():
    lib = (JS / "library.js").read_text(encoding="utf-8")
    assert "`${title.textContent}, ${kindWord.toLowerCase()}" in lib
    board = "".join((JS / n).read_text(encoding="utf-8") for n in ("whiteboard.js", "boards-gallery.js"))  # the gallery split out (INBOX 1772)
    assert '`${board.title}, ${isMapCard ? "map" : "board"}`' in board
