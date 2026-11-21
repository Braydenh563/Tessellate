"""Source text: L466, "C4 Connect words on sideways phone (no 480 step)". The
tab strip's room beside the header groups charged the header's `display: none`
h1 a flex gap it never takes, 7.2px at 844x390 (room 402.4 against 409.7
measured after). Part of this reads the shipped script, whose effect needs a
browser this suite does not run."""
import re

from tests._app_js import app_js_text


def _body(name):
    src = app_js_text()
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start)]


def test_row_space_skips_children_with_no_box():
    body = _body("tabRowSpace")
    assert "getClientRects().length" in body
    assert not re.search(r'classList\.contains\("hidden"\)', body)
