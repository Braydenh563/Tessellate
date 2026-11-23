"""Source text: a Notes card and a Library card draw the same border, fill and
corner (L767, owner decided 2026-11-12). Measured at 1440 after: both
rgb(227,225,221) on rgb(255,255,255) light, rgb(47,47,44) on rgb(30,30,28)
dark, 6.4px corners (before: Notes a transparent border on a tint, 8px)."""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    return text[start : text.index("}", start)]


def test_the_notes_card_uses_the_library_cards_tokens():
    library = _rule((CSS / "00-tokens-shell.css").read_text(), "\n.library-card")
    forms = (CSS / "01-forms-settings.css").read_text()
    notes = _rule(forms, "#entry-list:not(.is-rows) li")
    edge = _rule(forms, ".entry-list:where(#entry-list:not(.is-rows)) li")
    for prop, value in (("background", "var(--card)"), ("border-radius", "var(--radius-lg)")):
        assert f"{prop}: {value}" in library and f"{prop}: {value}" in notes
    assert "var(--glass-border)" in library and "border-color: var(--glass-border)" in edge


def test_the_library_rows_view_moved_with_its_bundle():
    lazy = (CSS / "library-lazy.css").read_text()
    assert re.search(r"\.library-grid\.library-list \{\s*columns: unset;", lazy)
    assert ".library-list .library-card {" in lazy
    assert ".library-grid.library-list {" not in (CSS / "00-tokens-shell.css").read_text()
