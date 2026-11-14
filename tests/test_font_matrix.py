"""Every Appearance font is swept (the owner 2026-10-11: "there's some
overflowing text in some places on different fonts like mono").

`scratchpad/ui-sweeps/fontmatrix.js` runs errors.js's text-fit check once per
font and theme at 1440, 1024 and 390, reading the fonts from `#font-seg`, so
a new font is in the matrix the day it is offered; `gate.sh --sweeps` runs it.
These hold the wiring, which the suite can see; the sweep holds the pixels."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEPS = ROOT / "scratchpad/ui-sweeps"
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/00-tokens-shell.css").read_text(encoding="utf-8")


def _fonts() -> list[str]:
    select = HTML.split('id="font-seg"')[1].split("</select>")[0]
    return re.findall(r'<option value="([a-z0-9-]+)"', select)


def test_the_matrix_reads_the_fonts_from_the_select():
    matrix = (SWEEPS / "fontmatrix.js").read_text(encoding="utf-8")
    assert "id=\"font-seg\"" in matrix and "errors.js" in matrix
    assert "1440,1024,390" in matrix and "light,dark" in matrix


def test_every_offered_font_has_a_stack():
    for font in _fonts():
        assert font == "system" or f':root[data-font="{font}"]' in CSS, font


def test_errors_and_lib_take_a_font_and_errors_checks_text_fit():
    errors = (SWEEPS / "errors.js").read_text(encoding="utf-8")
    lib = (SWEEPS / "lib.js").read_text(encoding="utf-8")
    assert "process.env.FONT" in errors and "process.env.FONT" in lib
    assert "TEXT_FIT_SRC" in errors and "checkMenus" in errors


def test_the_gate_runs_the_matrix():
    gate = (ROOT / "scripts/gate.sh").read_text(encoding="utf-8")
    assert re.search(r"for s in errors fontmatrix ", gate)


def _css(name: str) -> str:
    return (ROOT / "frontend/css" / name).read_text(encoding="utf-8")


def test_a_menu_row_cuts_its_words_inside_its_padding_and_titles_them():
    """The dashboard's ... menu, in mono: "Continue: Here are some refined,
    non-corny..." ran 33px past the row's padding (dashmono.js, 1426 against
    1393 at 1440). The kebabMenu item recipe: the row and its words flex with
    min-width 0, the words end in an ellipsis, and a cut row carries its full
    words in a title, never a smaller font."""
    css = _css("07-whiteboard-misc.css")
    assert re.search(r"\.menu-item,\s*\.menu-item > \.menu-item-words \{\s*min-width: 0;\s*\}", css)
    assert re.search(r"\.menu-item \.ph-text \{\s*min-width: 0;\s*overflow: hidden;\s*text-overflow: ellipsis;\s*white-space: nowrap;\s*\}", css)
    js = (ROOT / "frontend/js/sheets-selects.js").read_text(encoding="utf-8")
    assert js.count('menuRowFits(button, item.title || "");') == 2, "both menu builders"
    body = js[js.index("function menuRowFits(") : js.index("function kebabMenu(")]
    assert "words.scrollWidth > words.clientWidth" in body
    assert "font-size" not in body and "fontSize" not in body


def test_the_no_model_notice_steps_its_action_down_in_a_narrow_card():
    """Mono in a dashboard card: the words were squeezed to 14px beside the
    button and ran 58px out (probe at 1440). The words keep 12rem; the action
    wraps to a second row at the end."""
    css = _css("03-dashboard-widgets.css")
    assert re.search(r"\.ai-offline-note\.notice \{\s*flex-wrap: wrap;", css)
    assert re.search(r"\.ai-offline-text \{\s*flex: 1 1 12rem;\s*min-width: 0;", css)
