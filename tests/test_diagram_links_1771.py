"""The builder's connector rows (INBOX 1771).

The owner: the connector menu opened "on top of" the row instead of next to it; the rows should select or go to the blocks they
connect; the first row hid under the Ask bar; a label wrapped because Connect squeezed it; the Suggestions disclosure did not
read as one. Measured by scratchpad/ui-sweeps/diagram-links.js at 1440, 1100, 820 and 390.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    return source.split(head, 1)[1].split("\n  }\n", 1)[0]


# --- a: the menu opens beside its row ---------------------------------------------------------------


def test_the_connector_menu_is_placed_off_its_row_not_over_it():
    # Intent kept, mechanism moved (the hub's review of 1771): the row's ⋯ is a `kebabMenu` with `anchor`, so the recipe places it.
    selects = _read("sheets-selects.js")
    opener = _body(selects, "function kebabMenu(items, ariaLabel, { vertical = false, anchor = null } = {}) {")
    # Opening the menu focuses its first item, which scrolls the pane (the row moved 28px at 820x900, 676 to 648, under a menu placed
    # for the 676): the anchor is measured after the menu is open, and that box is the one the menu is placed against.
    assert opener.index("openActionMenu(menu, opener)") < opener.index("kebabMenu.beside(menu, anchor.getBoundingClientRect(), opener)")
    place = _body(selects, "kebabMenu.beside = (menu, row, opener) => {").split("\n};", 1)[0]
    # below if it fits, else above, else the larger of the two: never across the row; a menu taller than the room scrolls instead.
    assert place.index("[down, up]") < place.index("const below") < place.index("style.maxHeight = `") < place.index("row.top - gap - menu.")
    assert "maxHeight" in place and "escapeMenuToBody" in place
    assert "openMenuAtPoint" not in _read("diagram-joins.js") and "function beside" not in _read("diagram-joins.js")


# --- b: a connector row goes to the blocks it connects -----------------------------------------------


def test_a_connector_row_picks_the_arrow_and_goes_to_its_target_and_the_menu_is_its_own_kebab():
    builder = _read("diagram-builder.js")
    chip = _body(builder, "function joinChip(S, edge, index) {")
    assert 'joins(S, "go", { edge: S.m.edges[index] || edge, end: "to" })' in chip
    assert 'aria-label", `Go to ${to}.' in chip
    # the menu is a second control, a lazy `kebabMenu` (never a hand-drawn ⋯: test_icon_conventions) kept off the whole row.
    assert 'diagramModel.library.lazyKebab(' in chip and '"Change this connector", { anchor: line }' in chip
    assert 'joins(S, "items", S.m.edges[index] || edge)' in chip and "dots-three" not in builder
    assert chip.index('"go"') < chip.index("lazyKebab(")
    joins = _read("diagram-joins.js")
    go = _body(joins, 'function go(S, { edge, end = "to" }, h) {')
    assert "S.pickEdge?.(edge)" in go and "h.select(S, key)" in go and "scrollIntoView" in go
    assert 'go(S, { edge, end: "to" }, h)' in joins and 'go(S, { edge, end: "from" }, h)' in joins and "ask, go }" in joins
    pick = _read("diagram-edge-pick.js")
    assert "S.pickEdge = (edge) =>" in pick
    # a press on a connector row must not let go of the arrow it just picked.
    assert '.dgm-end, .dgm-join"' in pick


# --- e: Suggestions reads as a disclosure, and a name used again is one row --------------------------


def test_a_name_used_again_is_one_suggestion_that_numbers_them_all_in_one_step():
    from tests.test_diagram_ai import _run

    source = "flowchart TD\n  A[Start] --> B[Step]\n  B --> C[Step]\n  C --> D[Step]\n  D --> E[Step]\n  E --> F[Step]\n  F --> G[Step 2]\n"
    out = _run(source, """
      const found = ai.lint(m, o).filter((f) => /say Step/.test(f.text));
      const before = found.map((f) => [f.text, f.act, f.ops.length]);
      for (const f of found) ai.apply(m, f.ops, o);
      return { before, after: ai.lint(m, o).map((f) => f.text), names: m.nodes.map((n) => n.text) };
    """)
    r = out["result"]
    assert r["before"] == [["Five blocks say Step.", "Number them Step 1 to 6", 5]], r["before"]
    # "Step 2" was taken by another block, so the five are Step 1, 3, 4, 5, 6 and no pair is made.
    assert r["names"] == ["Start", "Step 1", "Step 3", "Step 4", "Step 5", "Step 6", "Step 2"]
    assert not [t for t in r["after"] if "say Step" in t]


def test_the_suggestions_row_turns_its_caret_and_its_rows_start_at_its_words():
    ai = _read("diagram-ai.js")
    assert "ph ph-caret-down contents-caret" in ai and "ph:caret-right Suggestions" not in ai
    assert 'aria-expanded", "false"' in ai
    assert ".dgm-ai-lints-head[aria-expanded=\"false\"] .contents-caret" in CSS
    assert re.search(r"\.dgm-ai-lints \{[^}]*padding-inline", CSS)


def test_the_list_hugs_its_content_when_stacked_and_the_rows_start_where_the_words_do():
    # Measured at 820x900 (the list under the picture in a narrow pane): the outline had 21 px of its 364 closed and 13 open, because the
    # list column's `max-block-size: 100%` had no row to resolve against and fell to its 12rem floor. Now 364 of 364, both ways.
    assert re.search(r"@container \(max-width: 599\.98px\) \{\s*\.dgm-listcol,\s*\.dgm-listcol > \.dgm-pane \{\s*max-block-size: none;", CSS)
    # The suggestion rows start where "Suggestions" does: 375.3 and 375.3 at 1440 (372.1 before: the caret is 1.15em, the button has a border).
    assert re.search(r"\.dgm-ai-lints \{[^}]*calc\(1px \+ var\(--space-2\) \+ 1\.15em \+ var\(--space-1\)\)", CSS)
    # A connector row keeps no padding at its end: "Can you reproduce it?" clipped 12 px at 1440, now 1.
    assert re.search(r"\.dgm-join \{[^}]*padding: 0 0 0 var\(--space-1\);", CSS)
