"""Line spacing and line width for reading (BACKLOG Sizing).

Three steps each over the numbers the reading surfaces already had (a note's
text at 1.55 and 84ch, a document's Read at 1.6 and 50em), as attribute rules
(a new custom property would break the stylesheet's falling count). Two Settings lists choose among three
values each, through `data-read-leading` and `data-read-measure` on the root,
the way Density does. A stored value no list offers falls back to the middle
one, so a hand-edited preference cannot leave a token invalid.
"""

from __future__ import annotations

from tests._help_text import help_more_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"
JS = ROOT / "frontend" / "js"
TOKENS = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")
CONTROLS = (JS / "settings-controls.js").read_text(encoding="utf-8")
ROWS = (JS / "settings-rows.js").read_text(encoding="utf-8")
AI_TOOLS = (JS / "ai-tools.js").read_text(encoding="utf-8")


def _rule(src: str, selector: str) -> str:
    at = src.index(selector + " {")
    return src[at : src.index("}", at)]


def test_each_step_has_a_rule_and_no_new_custom_property():
    """The stylesheet's custom-property count only falls (test_style_scale), so the
    steps are attribute rules over the numbers the surfaces already had."""
    forms = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    cards = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    editor = (CSS / "09-editor.css").read_text(encoding="utf-8")
    assert "max-width: 71ch" in _rule(forms, ':root[data-read-measure="narrow"] .entry-list:not(.is-rows) .entry-content')
    assert "max-width: 101ch" in _rule(forms, ':root[data-read-measure="wide"] .entry-list:not(.is-rows) .entry-content')
    assert "--doc-measure: calc(42.5em" in _rule(TOKENS, ':root[data-read-measure="narrow"]')
    assert "--doc-measure: calc(60em" in _rule(TOKENS, ':root[data-read-measure="wide"]')
    for tag, value in (("tight", "1.4"), ("roomy", "1.78")):
        assert f"line-height: {value};" in _rule(cards, f':root[data-read-leading="{tag}"] #entry-list .entry-content')
    for tag, plain, serif in (("tight", "1.44", "1.55"), ("roomy", "1.84", "1.98")):
        assert f"line-height: {plain};" in _rule(editor, f':root[data-read-leading="{tag}"] #doc-preview')
        assert f"line-height: {serif};" in _rule(editor, f':root[data-read-leading="{tag}"] .doc-serif #doc-preview')
    assert "--read-leading" not in TOKENS and "--read-measure" not in TOKENS


def test_two_lists_in_typography_and_layout():
    for ident, values in [("read-leading", ["tight", "normal", "roomy"]), ("read-measure", ["narrow", "standard", "wide"])]:
        at = INDEX.index(f'<select id="{ident}"')
        block = INDEX[at : INDEX.index("</select>", at)]
        assert re.findall(r'value="(\w+)"', block) == values
        assert f'"{ident}"' in CONTROLS[CONTROLS.index('for (const key of ["read-leading"') :][:200]
        assert f'$("{ident}").value = ' in SETTINGS
    # Both sit between Density and Corner rounding: one place for layout.
    assert INDEX.index('id="density-seg"') < INDEX.index('id="read-leading"') < INDEX.index('id="read-measure"') < INDEX.index('id="radius-slider"')


def test_the_choice_is_applied_validated_defaulted_mirrored_and_resettable():
    body = SETTINGS[SETTINGS.index("function applyAppearance") :][:1800]
    assert '"readLeading"' in body and '"readMeasure"' in body
    assert '"read-leading": "normal"' in SETTINGS and '"read-measure": "standard"' in SETTINGS
    assert '{ key: "read-leading", id: "read-leading" }' in ROWS and '{ key: "read-measure", id: "read-measure" }' in ROWS
    look = AI_TOOLS[AI_TOOLS.index("const OVERRIDABLE_KEYS") :][:500]  # LOOK_KEYS is built from it
    assert '"read-leading"' in look and '"read-measure"' in look
    small = INDEX[INDEX.index('id="read-measure-row"') :][:400]
    assert "column" in small


def test_the_guide_names_both():
    more = help_more_text()
    themes = more[more.index('"id": "themes"') :][:4500]
    assert "Line spacing" in themes and "Line width" in themes
