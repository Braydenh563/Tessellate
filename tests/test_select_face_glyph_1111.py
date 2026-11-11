"""Audit 1028 U27, left in a30f-1102.md:12: the Layout opener's face showed the name only.

An option that names a picture (`data-icon`) draws it in its list rows; the opener now
draws the chosen option's picture before its name too, from the same helper, decorative
(the name is the label), and takes it away when the chosen option has none.
"""

from tests._app_js import app_js_text


def _between(start: str, length: int) -> str:
    js = app_js_text()
    at = js.index(start)
    return js[at : at + length]


def test_one_helper_draws_the_picture_for_the_row_and_the_face() -> None:
    helper = _between("const optionGlyph = (option) => {", 400)
    assert "option?.dataset.icon" in helper
    assert "glyph.className = `ph ph-${name} ph-lead`;" in helper
    assert 'glyph.setAttribute("aria-hidden", "true");' in helper
    assert "const glyph = optionGlyph(option);" in _between("const buildOptionRow = (option) => {", 1200)


def test_the_opener_face_follows_the_chosen_option() -> None:
    sync = _between("const syncValue = () => {", 700)
    assert "faceGlyph?.remove();" in sync
    assert "faceGlyph = optionGlyph(chosen);" in sync
    assert "if (faceGlyph) opener.insertBefore(faceGlyph, valueText);" in sync
