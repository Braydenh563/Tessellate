"""The owner, 2026-10-10: "there's no way to vertically centre text". A text
box and a shape's words take top, middle or bottom from the Format panel's
Text tab (`scratchpad/ui-sweeps/wbvalign.js`: the text box stayed 11px from
its top whatever was asked before the schema named the field; 14/14 after)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from tessellate.api.routes_whiteboard import WhiteboardObjectData
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
HTML = index_html_text()
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_the_schema_keeps_the_vertical_place():
    # A field the schema does not name is dropped silently by Pydantic.
    assert WhiteboardObjectData(valign="middle").valign == "middle"
    assert WhiteboardObjectData(valign="bottom").valign == "bottom"
    with pytest.raises(ValidationError):
        WhiteboardObjectData(valign="sideways")


def test_the_text_tab_has_a_vertical_row_of_three():
    row = HTML[HTML.index('id="wb-fmt-valign"'):]
    row = row[:row.index("</span>")]
    for at in ("top", "middle", "bottom"):
        assert f'data-valign="{at}"' in row
    assert 'on("wb-fmt-valign", "click"' in FMT
    assert 'case "valign":' in FMT


def test_both_kinds_draw_it():
    assert "this.dataset.valign = d.data.valign" in WB
    assert 'label.dataset.valign === "top"' in WB
    assert '.wb-object-text[data-valign="middle"] .wb-text-content' in CSS
