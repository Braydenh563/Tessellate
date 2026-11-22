"""The colour well (DESIGN.md "A colour on a board"). The owner, 2026-10-11:
"it is difficult to change the border and fill colour to the same colour ...
cna there be liek a recent colours set in the colour picker popups?? ... I
tried to click the colour circle on the fill colour circle ... but it just
opened that colour picker menu instead of getting the colour."

Every board colour field opens one popover: a Recent row over the palette,
the fill and border of a shape as two labelled halves with Same as and Swap
(each one undo step), and an eyedropper that takes a colour from a press
instead of letting the press do what it would. The browser half is
`scratchpad/ui-sweeps/wbcolour-well.js`."""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
FORMAT = (JS / "whiteboard-format.js").read_text(encoding="utf-8")
BOARD = frontend_text("whiteboard.js")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
DESIGN = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.find("\n}\n", start)
    return source[start:end]


def test_every_board_colour_field_opens_the_well() -> None:
    fields = re.findall(r'<input type="color" id="(wb-[\w-]+)"[^>]*>', INDEX)
    assert len(fields) >= 12, fields
    for field in fields:
        tag = re.search(rf'<input type="color" id="{field}"[^>]*>', INDEX).group(0)
        assert "wb-color-picker" in tag, f"#{field} is a board colour without the well"
    assert "input[type=\"color\"].wb-color-picker" in FORMAT


def test_the_recent_row_is_eight_per_device_and_sits_over_the_palette() -> None:
    assert re.search(r"WB_RECENT_COLOURS_MAX\s*=\s*8\b", FORMAT)
    for name in ("wbRecentColours", "wbRememberColour"):
        body = _body(FORMAT, name)
        assert "prefs." in body and "try" in body and "catch" in body, name
    menu = _body(FORMAT, "wbOpenColourMenu")
    assert menu.index('wbColourHeading("Recent")') < menu.index('wbColourHeading("Colours")')


def test_swatches_come_from_the_one_swatch_recipe() -> None:
    menu = _body(FORMAT, "wbOpenColourMenu")
    assert menu.count("swatchPicker(") == 2
    assert "swatch-option" not in FORMAT.replace(".swatch-option", "")


def test_fill_and_border_are_named_paired_and_each_change_one_undo_step() -> None:
    menu = _body(FORMAT, "wbOpenColourMenu")
    for words in ('"Fill"', '"Border"', "Same as border", "Same as fill", '"Swap"'):
        assert words in menu, words
    assert '"tabs-line popup-kinds wb-colour-pair"' in menu and '"aria-selected"' in menu
    write = _body(FORMAT, "wbWriteColourPair")
    assert "wbRecordGesture" in write
    # The bar names both halves; the fill comes first.
    assert INDEX.index('data-wb-ctx="fill"') < INDEX.index('data-wb-ctx="ink"')
    assert 'id="wb-prop-color-word"' in INDEX and 'id="wb-fmt-stroke-word"' in INDEX
    assert INDEX.index('data-fmt="fill"') < INDEX.index('data-fmt="stroke"')
    # Dimmed, never disabled: a disabled colour field cannot open the well.
    assert 'getElementById("wb-prop-shapefill").disabled' not in BOARD
    assert "fillField.disabled" not in FORMAT


def test_the_eyedropper_takes_the_press_and_says_its_target() -> None:
    assert 'id = "wb-colour-eyedrop"' in FORMAT
    assert "Take a shape's border" in FORMAT
    sample = _body(FORMAT, "wbSampleColour")
    for kind in ('input[type="color"]', ".swatch-picker", ".sketch-group", ".wb-object"):
        assert kind in sample, kind
    assert "e.altKey || wbColourState.takeBorder" in FORMAT
    assert "stopImmediatePropagation" in FORMAT and "swallowClick" in FORMAT
    assert "html.wb-eyedropping" in LAZY


def test_the_well_has_its_recipe_row() -> None:
    assert "A colour on a board" in DESIGN
    assert "tests/test_wb_colour.py" in DESIGN
