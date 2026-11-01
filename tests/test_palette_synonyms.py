"""The command palette finds a feature by the words people use for it.

Audit 2026-10-05, UX-08: Ctrl+K "questions", "backup", "undo", "bin" and
"trash" each said "No matching command, note or document.", and "theme" found
nothing (only "dark" found "Toggle light/dark"). The recycle bin's only door
was Library, Filter, "Include the bin"; Questions was a Notes sub-tab. A row
now carries `keywords`, matched with its label, and the places that had no
row have one.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

_JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
#: The row registry stays in settings-panes.js (boot); the palette's own
#: window, `paletteMatches` with it, moved to the lazy app-palette.js.
SOURCE = (_JS / "settings-panes.js").read_text(encoding="utf-8") + (_JS / "app-features.js").read_text(encoding="utf-8") + (_JS / "app-palette.js").read_text(
    encoding="utf-8"
)


def _commands_body() -> str:
    start = SOURCE.index("function paletteCommands()")
    return SOURCE[start : SOURCE.index("\n}\n", start)]


def _searchable_rows() -> list[str]:
    """Each row's label and keywords, lower-cased, as the palette matches them."""
    rows = []
    for row in re.findall(r"\{[^{}]*label:[^{}]*\}", _commands_body()):
        label = re.search(r'label:\s*"([^"]*)"', row)
        keywords = re.search(r'keywords:\s*"([^"]*)"', row)
        rows.append(f"{label.group(1) if label else ''} {keywords.group(1) if keywords else ''}".lower())
    return rows


def test_the_palette_matches_keywords_as_well_as_the_label():
    #: The scorer reads them since Brief 90 (`paletteScore`, which
    #: `paletteMatches` reaches through `paletteRanked`).
    matches = SOURCE[SOURCE.index("function paletteScore(") :]
    matches = matches[: matches.index("\n}\n")]
    assert "row.keywords" in matches, "a row's keywords must be searched with its label"
    assert "paletteRanked(" in SOURCE[SOURCE.index("function paletteMatches(") :]


def test_the_words_the_audit_typed_each_find_a_row():
    rows = _searchable_rows()
    for word in ("questions", "backup", "restore", "undo", "redo", "bin", "trash", "deleted", "theme"):
        assert any(word in row for row in rows), f"Ctrl+K {word!r} finds no command"


def test_the_guided_tour_is_one_ctrl_k_away():
    """Found by the e2e flow pass (2026-10-05): Ctrl+K "tour" found only notes
    that happened to say "tour buses". The tour's doors were the Dashboard's
    first-run tile and Settings, Help; a person who skipped the welcome had
    to know that. A row now opens it."""
    rows = _searchable_rows()
    for word in ("tour", "walkthrough"):
        assert any(word in row for row in rows), f"Ctrl+K {word!r} finds no command"
    body = _commands_body()
    row = body[body.index("Take the guided tour") :]
    row = row[: row.index("}")]
    assert 'openTour("basics")' in row, row


def test_the_guide_is_one_ctrl_k_away():
    """CHAT_PLAN 9 row 3 (Brief 88): Ctrl+K "guide" found the tour and not
    the Guide. A row now opens it, through the reveal entry that opens it."""
    body = _commands_body()
    row = body[body.index('"ph:question Ask the Guide"') :]
    row = row[: row.index("}")]
    assert 'reveal: "atlas-help"' in row
    assert "guide" in row and "help" in row


# The palette weighs a typed prefix at half a pick (OPEN ledger 1408).

def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_1408_the_palette_learns_prefixes_at_half_weight():
    js = frontend_text("app-palette.js")
    assert "const picks = palettePrefixPicks(lowered);" in js
    body = _fn(js, "palettePrefixPicks")
    assert "typed.length < 2" in body and "n / 2" in body
