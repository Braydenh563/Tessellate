"""INBOX 1567 (the owner, 2026-11-03): "for the note capture subtab, should there be a clear for the title
only, the body only and clear all?? instead of just a clear all?"

The title and the body each get their own x (shown while the field has text); the existing Clear stays as
Clear all. Each is one undo step and its toast says what it cleared.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
COMPOSER_CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
CLEAR = (ROOT / "frontend" / "js" / "field-clear.js").read_text(encoding="utf-8")


def _rule(sheet: str, selector: str) -> str:
    found = [m.group(1) for m in re.finditer(r"(?:^|[}/])\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", sheet)]
    assert found, f"no rule for {selector}"
    return found[-1]



def _composer() -> str:
    start = INDEX.index('<div class="note-composer">')
    return INDEX[start : INDEX.index('id="entry-attachment-chips"', start)]


def test_the_title_and_the_body_each_have_their_own_x_and_clear_all_keeps_its_place():
    composer = _composer()
    for ident, field in (("capture-clear-title", "entry-title"), ("capture-clear-body", "entry-content")):
        tag = re.search(rf'<button[^>]*id="{ident}"[^>]*>', composer).group(0)
        classes = set(re.search(r'class="([^"]*)"', tag).group(1).split())
        assert {"ghost", "icon-only", "small", "field-clear", "field-clear-inline", "hidden"} <= classes
        assert "ph-x" in composer[composer.index(tag) : composer.index(tag) + 300]
        assert composer.index(tag) < composer.index(f'id="{field}"'), "the anchor sits before its field, at its top edge"
    all_tag = re.search(r'<button[^>]*id="capture-clear"[^>]*>', composer).group(0)
    assert 'title="Clear all"' in all_tag and 'aria-label="Clear all"' in all_tag


def test_each_x_is_a_field_clear_row_that_names_what_it_cleared_in_its_toast():
    assert re.search(r'button: "capture-clear-title",\s*fields: \["entry-title"\]', CLEAR)
    assert re.search(r'button: "capture-clear-body",\s*fields: \["entry-content"\]', CLEAR)
    assert 'said: "Cleared the title."' in CLEAR and 'said: "Cleared the note."' in CLEAR
    assert 'said: "Cleared everything."' in CLEAR
    assert "spec.said" in CLEAR
    # one undo step each, labelled by what it was
    assert re.search(r"pushUndo\(spec\.undoLabel", CLEAR)


def test_the_x_sits_on_the_field_top_right_and_the_text_keeps_clear_of_it():
    rule = _rule(COMPOSER_CSS, ".field-clear-anchor")
    assert "height: 0" in rule and "position: relative" in rule
    inline = _rule(COMPOSER_CSS, ".field-clear-anchor > .field-clear-inline")
    assert "position: absolute" in inline and "z-index" in inline
    assert "padding-right: calc(var(--target-min) + var(--space-3))" in _rule(COMPOSER_CSS, ".note-composer > #entry-title")
