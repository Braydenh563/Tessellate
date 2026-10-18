"""draw.io's Text tab, the cheap half (WHITEBOARD_PLAN, "The draw.io programme"
section 2; whiteboard-1018): underline, strikethrough and a font face on a
shape's words and a text box, the three rows the Text tab lacked, plus
"Clear formatting" and the two font-size steps as board commands.

A text box keeps `underline`, `strike` and `font_family` on its object data
(the schema must name them or Pydantic drops them silently, the lesson of
`test_wb_valign.py`); a shape keeps `label_underline`, `label_strike` and
`label_font` in its sketch data, which the server leaves opaque. Measured in
the app by the sweep named in `agent-remaining/whiteboard-1018.md`."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from tessellate.api.routes_whiteboard import WhiteboardObjectData

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def test_the_schema_keeps_the_new_text_fields():
    data = WhiteboardObjectData(underline=True, strike=True, font_family="serif")
    assert (data.underline, data.strike, data.font_family) == (True, True, "serif")
    for face in ("serif", "mono", "wide", "hand"):
        assert WhiteboardObjectData(font_family=face).font_family == face
    with pytest.raises(ValidationError):
        WhiteboardObjectData(font_family="comic-sans; background:url(x)")


def test_the_text_tab_has_the_rows():
    text = HTML[HTML.index('data-format-panel="text"'):HTML.index('data-format-panel="arrange"')]
    assert 'id="wb-fmt-underline"' in text and 'id="wb-fmt-strike"' in text
    assert 'id="wb-fmt-font"' in text
    for face in ("serif", "mono", "wide", "hand"):
        assert f'value="{face}"' in text
    assert 'data-fmt="text"' in text[text.index('id="wb-fmt-font"') - 120:text.index('id="wb-fmt-font"')]


def test_the_panel_reads_and_writes_them():
    for field in ("underline", "strike", "font"):
        assert f'case "{field}":' in FMT
    assert 'on("wb-fmt-font", "change"' in FMT
    assert 'label_underline' in FMT and 'label_strike' in FMT and 'label_font' in FMT
    assert 'wb-fmt-underline' in FMT and 'wb-fmt-strike' in FMT


def test_a_shape_and_a_text_box_draw_them():
    assert "label.style.textDecoration" in WB
    assert "label.style.fontFamily" in WB
    # The wrap is measured in the face and weight it is drawn in.
    assert "${label.style.fontFamily}|${label.style.fontWeight}" in WB
    assert '.style("text-decoration"' in WB
    assert '.style("font-family"' in WB
    assert "const WB_ITEM_FONTS" in WB


def test_reset_style_takes_them_off():
    for key in ("label_underline", "label_strike", "label_font"):
        assert f'"{key}"' in WB[WB.index("const WB_SKETCH_RESET_KEYS"):WB.index("const WB_OBJECT_RESET_KEYS")]
    reset = WB[WB.index("const WB_OBJECT_RESET_KEYS"):][:300]
    for key in ("underline", "strike", "font_family"):
        assert f'"{key}"' in reset


def test_the_commands_exist():
    for command in ("clear-format", "font-bigger", "font-smaller"):
        assert f'id: "{command}"' in CMD
    assert "function wbClearTextFormat" in FMT
    assert "function wbStepFontSize" in FMT
