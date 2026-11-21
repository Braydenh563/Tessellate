"""L-world-class-129, WORLD_CLASS decision 64: the note menu is grouped Atlas,
structure, share, destructive, in that order, with under nine rows showing.
Measured before: ten rows (eleven with Headings); after: eight."""

from __future__ import annotations

from pathlib import Path

TEXT = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "entry-menu.js").read_text(encoding="utf-8")


def _assembly() -> str:
    start = TEXT.index("const named = (items, word)")
    return TEXT[start : TEXT.index("menu.appendChild(buildMenuItemButton(danger));", start)]


def test_the_groups_come_in_decision_64s_order():
    body = _assembly()
    marks = ['"ph:sparkle Atlas"', "buildMenuItemButton(select)", '"ph:link Connect"', '"ph:plus Add"', '"ph:export Share and export"', "buildMenuItemButton(archive)"]
    at = [body.index(m) for m in marks]
    assert at == sorted(at)
    assert body.count("rule()") == 3


def test_under_nine_rows_show_at_the_top():
    body = _assembly() + "menu.appendChild(buildMenuItemButton(danger));"
    rows = body.count("menu.appendChild(buildMenu")
    assert rows <= 8, rows


def test_share_holds_who_reads_it_and_where_it_goes():
    share = TEXT[TEXT.index("const shareWords = [") :].split("\n", 1)[0]
    for word in ("Add to a document", "Add to a board or map", "Expand into a document", "Copy wiki link"):
        assert f'"{word}"' in share
    assert "[select, move, headings, connections].includes(item)" in TEXT


def test_a_missing_row_is_skipped_not_thrown():
    """Review 5907752577: rows are found by label, so a renamed one was
    `undefined` and `buildMenuItemButton(undefined)` threw, emptying the menu."""
    body = _assembly()
    assert "if (select) menu.appendChild(" in body and "if (move) menu.appendChild(" in body
    assert "[connections, headings, ...connect].filter(Boolean)" in body
