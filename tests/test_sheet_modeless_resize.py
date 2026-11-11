"""sm-1111 row 24: a modeless sheet (the Guide, the Clock) re-reads its width
band while open. Measured before: opened at 800 and shrunk to 390 it kept
`sheet-modeless` (no scrim, `pointer-events: none` on the overlay) at phone
width, where the sheet is the window and must be modal."""

from pathlib import Path

SHELL = (Path(__file__).resolve().parent.parent / "frontend/js/phone-shell.js").read_text(encoding="utf-8")
SHEET = SHELL[SHELL.index("function openSheet("):]
SHEET = SHEET[: SHEET.index("\n}\n")]


def test_modeless_is_reapplied_when_the_width_band_changes():
    assert "const wide = matchMedia(" in SHEET
    assert "const applyModeless" in SHEET
    assert 'wide.addEventListener("change", applyModeless)' in SHEET
    # and the listener leaves with the sheet
    assert 'wide.removeEventListener("change", applyModeless)' in SHEET


def test_modal_attribute_follows_the_class():
    body = SHEET[SHEET.index("const applyModeless") :]
    body = body[: body.index("};")]
    assert 'removeAttribute("aria-modal")' in body and 'setAttribute("aria-modal", "true")' in body
