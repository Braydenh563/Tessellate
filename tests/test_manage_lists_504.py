"""The tag and category managers gain sort, a hardly-used filter, look-alike
merges, a count that opens the notes, and bulk colour and delete (INBOX 504).

The owner: "also add more capablilty and utility to the manage tags and
categories panels." Driven in Chromium by the session's `manage504.js` (1440
light, 390 dark, axe on both panels); this is the half the suite can see, plus
the look-alike rule run as JavaScript.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
TAGS = (JS / "tag-manager.js").read_text(encoding="utf-8")
CATS = _js_scope.unwrapped((JS / "categories-panel.js").read_text(encoding="utf-8"))


def _body(text: str, signature: str) -> str:
    start = text.index(signature)
    return text[start : text.index("\n}\n", start)]


def test_both_panels_share_one_tool_row_and_one_set_of_helpers() -> None:
    for source in (TAGS, CATS):
        assert "...manageListControls({" in source
        #: Categories draw the server's tidy proposals there (world-class row
        #: 11, `drawCategoryTidy`), in the same box and the same row shape.
        assert "drawManageSuggestions(state.suggestBox" in source or "drawCategoryTidy(state.suggestBox" in source
        assert "manageCountButton(" in source
        assert "manageSorted(" in source
    # The categories panel reads the helpers from the tag manager's module.
    opener = _body(CATS, "async function openManageCategories(focusName = null)")
    assert 'ensureModule("tagManager")' in opener
    # Defined once, in the tag manager.
    assert TAGS.count("function manageLookAlikes(") == 1 and "function manageLookAlikes(" not in CATS


def test_the_sort_is_remembered_safely() -> None:
    stored = _body(TAGS, "function manageStored(key, fallback)")
    assert "try {" in stored and "prefs.get(" in stored
    assert 'manageStored("manage-tags-sort", "count")' in TAGS
    assert 'manageStored("manage-categories-sort", "name")' in CATS


def test_the_count_opens_the_notes_and_stays_out_of_the_tab_order() -> None:
    count = _body(TAGS, "function manageCountButton(count, onShow)")
    assert "button.tabIndex = -1" in count and "event.stopPropagation()" in count
    assert "manageCountButton(count, () => showTagNotes(name))" in TAGS
    assert "manageCountButton(meta.count, () => showCategoryNotes(meta.name))" in CATS


def test_bulk_delete_asks_once_and_bulk_colour_has_one_undo() -> None:
    footer = _body(CATS, "function drawManageCategoryFooter(footer, state, redraw)")
    assert "deleteCategoriesFromPanel(metas)" in footer and "colourCategoriesFromPanel(" in footer
    delete = _body(CATS, "async function deleteCategoriesFromPanel(metas)")
    assert delete.count("chooseCategorySheet(") == 1 and "offerCategoryUndo(" in delete
    colour = _body(CATS, "function colourCategoriesFromPanel(metas)")
    #: Brief 51 folded the bulk colour into `offerUndo` (status.js), which is
    #: `pushUndo` plus the toast's Undo.
    assert "offerUndo(" in colour and "before.get(name)" in colour


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_look_alikes_group_case_spacing_and_plurals() -> None:
    script = "\n".join(
        [
            _body(TAGS, "function manageLookAlikeKey(name)") + "\n}",
            _body(TAGS, "function manageLookAlikes(names, countOf)") + "\n}",
            "const counts = {Idea: 3, ideas: 1, 'to-do': 1, todo: 4, Recipe: 2, recipes: 2, glass: 1, gas: 1, Stories: 1, story: 2, work: 5};",
            "console.log(JSON.stringify(manageLookAlikes(Object.keys(counts), (n) => counts[n])));",
        ]
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    groups = json.loads(out)
    assert ["Idea", "ideas"] in groups
    assert ["todo", "to-do"] in groups  # the busiest first: it is the one kept
    assert ["Recipe", "recipes"] in groups
    assert ["story", "Stories"] in groups
    # "glass" is not the plural of "glas", and nothing pairs with "work".
    assert not any("glass" in group or "work" in group for group in groups)
