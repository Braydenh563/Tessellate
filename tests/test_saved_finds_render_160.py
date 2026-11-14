"""Saved searches are drawn when the Notes surface is built (L-world-class-160).

`search.js` loads lazily, after the preferences say there are saved searches,
and its closing `renderSavedFinds()` ran before the Notes surface (and so
`#saved-finds`) existed: after a reload the sidebar showed no saved searches
until one was saved again. Measured at 5,000 notes on 2026-11-14: 0 rows
before, 3 after; the row menu is 198 x 83 px inside a 1440 x 900 window with
two items (Rename, Forget), and a click on a row opens the finder with its
words ("garden": 30 results in 899 ms).
"""

from __future__ import annotations

import re
from pathlib import Path

SEARCH = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "search.js").read_text(encoding="utf-8")


def test_the_surface_callback_draws_the_saved_searches():
    block = re.search(r'onSurface\("notes", \(\) => \{(.*?)\n\}\);', SEARCH, re.S)
    assert block, "search.js no longer wires the Notes surface"
    assert "renderSavedFinds()" in block.group(1)


def test_the_row_menu_is_the_kebab_recipe_with_rename_and_forget():
    rows = SEARCH[SEARCH.index("function renderSavedFinds") : SEARCH.index("renderSavedFinds();\n\n//: L592")]
    assert "kebabMenu(" in rows
    assert "Rename" in rows and "Forget" in rows
    assert 'openFinder(item.query, { kind: "" })' in rows
