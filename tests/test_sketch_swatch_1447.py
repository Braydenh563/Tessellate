"""INBOX 1447: "If i delete a colour swatch in the quick sketch, it is hard to
resave it as a colour swatch, also make sure th delete button isnt so big the
user can fumble delete it".

Measured before (1440x900, three recent colours): the remove button was 24x24
and sat over the swatch's right two thirds and part of the next swatch (the
swatch's own centre was intercepted by it), and nothing brought a removed
colour back except picking it again by eye. After: the x is 16x16 in a cell of
its own (overlap with its swatch 0 px2, with the next 0 px2, 12 px from each
swatch edge so a 24px circle round it meets no other target); a removal says
so with an Undo; Save colour (the plus after the picker) re-adds the current
colour and is `aria-disabled` while it is already a swatch.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAD = (ROOT / "frontend" / "js" / "sketch-pad.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "sketch-pad.css").read_text(encoding="utf-8")
MEDIA = (ROOT / "frontend" / "js" / "media.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = PAD.index(f"function {name}(")
    return PAD[start : PAD.index("\n  }\n", start)]


def _rule(selector: str) -> str:
    start = CSS.index(f"\n{selector} {{") + 1
    return CSS[start : CSS.index("}", start)]


def test_removing_a_swatch_offers_undo_that_puts_it_back_in_place() -> None:
    body = _fn("forgetColour")
    assert 'S.host.toastAction(' in body and '"Undo"' in body
    assert "slice(0, at)" in body and "slice(at)" in body, "Undo restores the colour where it was"
    assert "toastAction: (message, label, run) => toastAction(message, label, run)" in MEDIA


def test_the_current_colour_has_a_save_colour_plus() -> None:
    assert 'title: "Save colour"' in PAD and '"data-sp": "keep"' in PAD
    assert "rememberColour(current)" in _fn("keepColour")
    paint = _fn("paintKeep")
    assert "aria-disabled" in paint and "already a swatch" in paint
    assert "paintKeep(current)" in _fn("paintWells"), "the state follows the colour"
    # The picker no longer wears the plus, so the two controls are not the same picture.
    custom = PAD[PAD.index('const custom = h("label"') :][:600]
    assert 'icon("eyedropper")' in custom and 'icon("plus")' not in custom


def test_the_remove_x_is_small_beside_the_swatch_never_over_it() -> None:
    rule = _rule(".sp-unpick")
    assert "position: absolute" not in rule, "an overlay covers the swatch's hit area"
    size = re.search(r"width: var\(--space-(\d)\)", rule)
    assert size and int(size.group(1)) <= 6, "the x stays small (16px at the default density)"
    item = _rule(".sp-recent-item")
    assert "display: inline-flex" in item and "gap: var(--space-1)" in item, "spacing carries the 24px floor"
    assert "visibility: hidden" in rule and ".sp-recent-item:is(:hover, :focus-within) .sp-unpick" in CSS


def test_the_pad_help_names_undo_and_save_colour() -> None:
    colours = PAD[PAD.index('["Colours", ') :]
    colours = colours[: colours.index("\"],")]
    assert "Undo" in colours and "plus" in colours


def test_the_remove_x_is_a_quiet_glyph_not_a_badge() -> None:
    """INBOX 1450, the owner: "that x delete button is off in design". A 12.9px
    glyph filled its 16px disc, and a tap on a touch screen left the hover fill
    on. The glyph is the smallest text step and the fill comes only with a real hover."""
    assert re.search(r"\.sp-unpick > :is\(i, svg\) \{\s*font-size: var\(--text-xs\);", CSS)
    assert re.search(r"@media \(hover: hover\) \{\s*\.sp-unpick:hover \{\s*background: var\(--ghost-btn-bg\);", CSS)
