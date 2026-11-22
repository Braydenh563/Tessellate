"""Whiteboard follow-ups (canvasdepth and canvasui, OPEN.md).

1. An item on a hidden or locked named layer is hidden or locked whatever its
   own flag says, so its own eye or lock changed nothing. The layer wins: the
   row's button says so and the press points at the layer (the simpler of the
   two ways out: no second per-item override to explain).
2. A hollow end (diamond, circle, square) drew the shaft through its middle.
   The shaft now stops at the shape's far edge.
"""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WB = frontend_text("whiteboard.js")
LIB = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")


def _slice(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_a_layered_items_eye_and_lock_say_the_layer_decides():
    assert "function wbLayerOwning(kind, item, flag)" in LIB
    assert 'wbLayerOwning(row.kind, row.item, "hidden")' in LIB and "Hidden by its layer," in LIB
    assert 'wbLayerOwning(row.kind, row.item, "locked")' in LIB and "Locked by its layer," in LIB
    for toggle, flag in (("wbLayerToggleHidden", "hidden"), ("wbLayerToggleLock", "locked")):
        body = _slice(LIB, f"async function {toggle}(li)", "\n}\n")
        assert f'wbLayerOwning(kind, item, "{flag}")' in body and "wbLayerSaysOwner(" in body
        assert body.index("wbLayerSaysOwner(") < body.index("wbSet"), "the layer is checked before anything is saved"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_a_hollow_end_stops_the_shaft_at_its_far_edge():
    code = (
        _slice(WB, "const WB_CAP_SIZE_SCALE", "function wbCapSizeFields(")
        + _slice(WB, "const WB_HOLLOW_INSET", "function wbCapPath(")
        + "\nconsole.log(JSON.stringify(["
        + "wbShaftEnd({x:200,y:0},{x:0,y:0},'diamond',18),"
        + "wbShaftEnd({x:200,y:0},{x:0,y:0},'circle',18),"
        + "wbShaftEnd({x:200,y:0},{x:0,y:0},'square',18),"
        + "wbShaftEnd({x:200,y:0},{x:0,y:0},'triangle',18),"
        + "wbShaftEnd({x:200,y:0},{x:0,y:0},'none',18),"
        + "wbShaftEnd({x:10,y:0},{x:0,y:0},'diamond',18)]));"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    diamond, circle, square, triangle, none, short = json.loads(out)
    assert diamond["x"] == pytest.approx(200 - 19.8)
    assert circle["x"] == pytest.approx(200 - 12)
    assert square["x"] == pytest.approx(200 - 18 * 2 / 2.6)
    assert triangle == {"x": 200, "y": 0} and none == {"x": 200, "y": 0}
    assert short["x"] == pytest.approx(1.0), "a short segment keeps a stub"


def test_every_link_path_builder_trims_its_shaft():
    for fn in ("wbLinkPathD", "wbElbowPathD", "wbCurvePathD"):
        body = _slice(WB, f"function {fn}(", "\n}\n")
        assert "wbShaftEnd(" in body, fn
    assert len(re.findall(r"wbShaftEnd\(", WB)) >= 9
