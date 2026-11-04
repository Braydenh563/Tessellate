"""The calculator window fits the calculator (INBOX 1622, the owner, 2026-11-04: "fix the sizing of the calculator
window to fit the calculator better?? also I still dont like these pill buttons").

Browser numbers (the card's box against its content, scrollHeight against clientHeight, radii) are in the CHANGELOG
line, measured by a sweep at 1440 by 900 and 1024 by 768, light and dark; these hold what a file can say.
"""

from __future__ import annotations

import re

from tests.test_calc_panel_1102 import EDITOR, EDITOR_CSS, KIT, KIT_CSS, _rule


def test_the_kind_and_angle_toggles_are_tab_strips_not_pills() -> None:
    """DESIGN.md, "A popup that chooses a kind": no pills in popups (INBOX 715); the owner said it again for the calculator."""
    seg = KIT.split("  seg(label, choices, value, onChange) {", 1)[1].split("\n  },", 1)[0]
    assert '"tabs-line popup-kinds calc-seg"' in seg
    assert '"seg ' not in seg and "aria-pressed" not in seg
    assert 'setAttribute("role", "tablist")' in seg and 'setAttribute("role", "tab")' in seg and "aria-selected" in seg
    assert "is-pointer" not in KIT and "is-pointer" not in KIT_CSS, "the ring is the strip's :focus-visible alone"
    head = _rule(KIT_CSS, ".calc-head .calc-seg")
    assert "box-shadow: none" in head, "no second hairline under the head row"
    tab = _rule(KIT_CSS, ".calc-head .calc-seg > button")
    assert "var(--space-3)" in tab and not re.search(r"\d+px|\d+rem", tab), "tokens only"


def test_the_card_fits_its_content_and_the_panes_share_one_cell() -> None:
    card = _rule(KIT_CSS, ".sheet-card.calc-card")
    assert "height: auto" in card and "max-height: min(" in card
    panes = _rule(KIT_CSS, ".calc-panes")
    assert "display: grid" in panes
    pane = _rule(KIT_CSS, ".calc-pane")
    assert "grid-area: 1 / 1" in pane
    #: A hidden pane keeps its box (`.hidden` is `display: none !important`), so the card is the tallest of them.
    assert "visibility: hidden" in _rule(KIT_CSS, ".calc-pane.is-off")
    assert 'pane.classList.toggle("is-off"' in KIT and 'classList.toggle("hidden", key' not in KIT
    #: The Equation editor (2400px with its palette) never sets the card's height; it scrolls inside the row.
    equation = _rule(KIT_CSS, ".calc-pane.calc-equation")
    assert "contain: size" in equation and "overflow-y: auto" in equation
    assert "flex-shrink: 0" in _rule(KIT_CSS, ".calc-pane > *")


def test_scientific_lays_its_keys_beside_the_digits() -> None:
    """Stacked, Scientific was 767px tall and scrolled at 1024 by 768; side by side it is 669px."""
    assert 'pane.classList.toggle("is-sci", on)' in KIT
    block = KIT_CSS.split("@media (min-width: 40rem) {", 1)[1].split("\n}\n\n", 1)[0]
    assert ".calc-pane.is-sci" in block and "grid-template-columns: 1fr 1fr" in block
    assert re.search(r"\.calc-keys-sci \{\s*grid-column: 1;", block)
    assert re.search(r"\.calc-keys:not\(\.calc-keys-sci\) \{\s*grid-column: 2;", block)
    assert "width: min(40rem, 94vw)" in block


def test_the_figure_and_the_copy_button_share_one_centre_line() -> None:
    """INBOX 1622, "are that = and 36 aligned??": baseline alignment put the figure 2.9px above the 28px button's centre
    and the button ran 2.4px past the box. Now the centres differ by 0.05px and the button sits inside the box."""
    row = _rule(KIT_CSS, ".calc-figure-row")
    assert "align-items: center" in row and "align-items: baseline" not in row
    assert "min-height: var(--control-h)" in row


def test_inline_and_display_look_different_in_the_field() -> None:
    """INBOX 1622: the two options wrote different TeX but the field looked the same. Inline is text-sized and left,
    display is larger and centred (glyph centre 718.5 against the field's 720 at 1440, and x 483 inline)."""
    modes = EDITOR.split("function mathEditorModes(", 1)[1].split("\n}\n", 1)[0]
    assert 'className = "tabs-line popup-kinds math-editor-mode"' in modes and "seg-fill" not in modes
    assert 'setAttribute("data-display", String(on))' in modes
    assert "host.dataset.display = String(display)" in EDITOR
    inline = _rule(EDITOR_CSS, '.math-editor[data-display="false"] math-field.math-field')
    shown = _rule(EDITOR_CSS, '.math-editor[data-display="true"] math-field.math-field')
    assert "var(--text-lg)" in inline and "var(--text-h1)" in shown
    assert "justify-content: center" in _rule(EDITOR_CSS, '.math-editor[data-display="true"] math-field.math-field::part(content)')
