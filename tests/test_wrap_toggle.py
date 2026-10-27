"""The wrap toggle on code and table cards (the owner, 2026-10-27: "can you add
a button to toggle wrap text in tables or code blocks??").

Measured in the browser by `scratchpad/ui-sweeps/wraptoggle.js` (a reply at
1280 and 390, dark), `wrapnote.js` (a note's Read view) and `wrapfull.js` (a
table's full view), scrollWidth against clientWidth before and after a press:

- reply at 1280: table 679 over 656 then 656 over 656, code 1245 over 656 then
  656 over 656; at 390: table 679 over 223 then 223, code 1245 over 223 then 223;
- Read view at 600: table 599 over 538 then 538, code 1245 over 538 then 538.

These tests keep the shapes those numbers depend on from being undone.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_one_builder_makes_the_wrap_toggle_and_it_is_a_pressed_toggle() -> None:
    src = _read(JS / "markdown.js")
    body = src[src.index("function wrapToggle(") :].split("\n}\n", 1)[0]
    assert 'button.setAttribute("aria-label", "Wrap lines")' in body
    assert 'button.setAttribute("aria-pressed", String(on))' in body
    assert '"Don\'t wrap"' in body and '"Wrap lines"' in body
    assert "ph:text-align-left" in body
    # The choice is remembered per kind, through the prefs store.
    assert "`wrap-${kind}`" in body and "prefs.set(key" in body and 'prefs.bool(key, false)' in body
    # Only the recipe makes the class: a second hand-built toggle is a second shape.
    for path in sorted(JS.glob("*.js")):
        if path.name == "markdown.js":
            continue
        assert "wrap-toggle" not in _read(path), f"{path.name} builds its own wrap toggle"


def test_table_and_code_cards_both_wear_it_beside_copy() -> None:
    markdown = _read(JS / "markdown.js")
    assert 'wrapToggle(\n    "table"' in markdown
    table_actions = markdown[markdown.index("actions.append(\n    wrap.button,") :].split(");", 1)[0]
    assert table_actions.index("wrap.button") < table_actions.index('"ph:copy Copy"')
    navigation = _read(JS / "navigation.js")
    assert 'wrapToggle("code"' in navigation
    assert "actions.append(wrap.button, copy, save)" in navigation
    assert 'block.dataset.wrap = wrapOn ? "on" : "off"' in navigation


def test_the_table_fit_row_left_the_menu_for_the_head() -> None:
    """Replace, do not layer: the ⋯ no longer carries a second copy of the switch."""
    markdown = _read(JS / "markdown.js")
    assert "Fit to panel" not in re.sub(r"//:.*", "", markdown)
    assert "Actual size" not in re.sub(r"//:.*", "", markdown)
    assert "fit.click()" not in markdown
    # Full view still starts fitted (INBOX 179), and leaving restores the reader's choice.
    assert 'setTableView(colSizes || rowSizes ? "sized" : "fit")' in markdown
    assert "setTableView(bubbleView())" in markdown
    # A press inside full view is not what the next bubble starts as.
    assert '() => !block.classList.contains("is-full")' in markdown


def test_a_wrapped_code_card_breaks_long_lines_and_does_not_scroll() -> None:
    css = _read(CSS / "05-sidebars-themes.css")
    start = css.index('.code-block[data-wrap="on"] pre {')
    rule = css[start : css.index("}", start)]
    assert "white-space: pre-wrap" in rule
    assert "overflow-wrap: anywhere" in rule
    assert "overflow-x: hidden" in rule
    # The pressed state of a head toggle reads as the accent's soft fill.
    assert '.code-actions > .code-copy[aria-pressed="true"]' in css


def test_the_recipe_index_names_the_card_head_and_the_guide_says_where_it_is() -> None:
    design = _read(ROOT / "docs" / "DESIGN.md")
    assert "wrapToggle" in design and "tests/test_wrap_toggle.py" in design
    help_text = _read(ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py")
    assert '"id": "wrap-lines"' in help_text and "Wrap lines button" in help_text
