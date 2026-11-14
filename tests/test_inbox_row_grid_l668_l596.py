"""L668 rowActions in tidy rows, L596 inbox grid rows."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_tidy_rows_use_row_actions():
    assert "rowActions(actions" in _text("categories-panel.js")
    assert "rowActions([" in _text("tag-manager.js")
    inbox = _text("suggestions-inbox.js")
    assert "rowActions(actions" in inbox
    assert "smallButton(\"ph:arrows-merge Merge\"" not in inbox


def test_names_and_types_rows_use_the_links_grid():
    inbox = _text("suggestions-inbox.js")
    assert 'row.className = "link-suggestion inbox-row"' in inbox
    assert inbox.count("inboxGridRow(") >= 3  # the definition and two callers
