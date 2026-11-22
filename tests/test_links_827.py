"""INBOX 827 L3 to L6: the Links tab's look, card, folders and views (`library-links.js`).

Static checks of what the sweeps measured at 1440 and 390 (`l36*.js`: a chosen colour tints the mark and
the row in every palette, the card is two clamped lines and a reading column of 448px at 16px on 25.6px,
a link dropped on a folder files it, on another link files both, a folder dropped on one nests it, a
double-click renames in place, cards are five 267px columns, Duplicates finds the www and tracking twins).
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.repo import bookmarks
from tests._js_scope import exported, is_wrapped

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


JS = _read("frontend", "js", "library-links.js")
LIB = _read("frontend", "js", "library.js")
CSS = _read("frontend", "css", "library-lazy.css")
HTML = _read("frontend", "index.html")


def test_the_file_is_wrapped_and_exports_one_name():
    assert is_wrapped(JS) and exported(JS) == {"LinkShelf"}


def test_it_loads_with_library_js_and_after_it():
    app = _read("frontend", "js", "app.js")
    line = re.search(r"libraryList: \[([^\]]*)\]", app).group(1)
    assert line.index("/js/library.js") < line.index("/js/library-links.js")


def test_every_colour_the_server_takes_is_drawn_and_offered():
    palette = JS.split("const LOOKS = {", 1)[1].split("};", 1)[0]
    assert tuple(re.findall(r"(\w+): \"oklch\(", palette)) == bookmarks.COLORS


def test_a_chosen_colour_beats_the_flat_looks():
    assert re.search(r":root \.bookmark-mark\.has-look \{[^}]*color-mix\(in oklab, var\(--swatch\)", CSS)


def test_the_only_style_the_file_writes_is_the_swatch_property():
    """The CSP forbids style attributes; the CSSOM is fine, and only for the palette's own `--swatch`."""
    assert "style=" not in JS and "cssText" not in JS
    assert set(re.findall(r"\.style\.(\w+)\(\"([^\"]+)\"", JS)) == {("setProperty", "--swatch"), ("removeProperty", "--swatch")}


def test_the_row_uses_the_shelf_for_mark_drag_card_and_menu():
    for needle in ("LinkShelf.fillMark(", "LinkShelf.wireRow(", "LinkShelf.detailsCard(", "LinkShelf.chooseBookmarkLook(", "LinkShelf.afterSave()"):
        assert needle in LIB, needle
    assert "ph:palette Icon and colour" in LIB and "ph:bookmark-simple Read later" in LIB


def test_the_chips_are_folders_that_drag_and_take_drops():
    for needle in ("LinkShelf.folderChip(", "LinkShelf.wireChip(allChip, null)", "LinkShelf.scopeBar()", "LinkShelf.duplicateSets()"):
        assert needle in LIB, needle
    assert 'id="bookmark-folder-bar"' in HTML and 'id="bookmark-view"' in HTML
    assert 'option value="cards"' in HTML


def test_folders_nest_one_level_and_rename_in_place():
    assert 'to.split("/").length > 2' in JS
    assert 'event.key === "F2"' in JS and "event.detail >= 2" in JS


def test_the_user_facing_word_is_folder_not_group():
    assert "New folder</button>" in HTML and "Manage folders</button>" in HTML
    assert "New group</button>" not in HTML and "Manage groups</button>" not in HTML
    for old in ('"ph:folder-simple Move to group', 'dialogHead("Manage groups"', "Manage bookmark groups"):
        assert old not in LIB, old


def test_duplicates_ignore_scheme_www_slash_fragment_and_tracking():
    body = JS.split("function sameKey(raw) {", 1)[1].split("function duplicateSets", 1)[0]
    for needle in ("www", "utm_", "fbclid", "pathname.replace(/\\/+$/"):
        assert needle in body, needle


def test_a_deleted_link_comes_back_with_its_look():
    assert 'icon: b.icon || ""' in LIB and 'color: b.color || ""' in LIB


def test_the_guide_topic_says_what_was_built():
    from tests._help_text import help_more_text

    text = help_more_text()
    for phrase in ("Icon and colour", "Show page text", "Cards", "Duplicates", "double-click or F2 renames", "nest it, one level", "Read later"):
        assert phrase in text, phrase
    assert "Add bookmark" in HTML and "Duplicates appears" in HTML
